import numpy as np
import tensorflow as tf
import gym
import time
import random
import os
import argparse
import collections
import pickle

from common.cmd_util import make_vec_env
from common.vec_env.vec_frame_stack import VecFrameStack
from common.logger import Logger

from termcolor import cprint, colored

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dir_name', type=str,
                        default='default', help='Dir name')
    parser.add_argument('--data_dir', type=str, default='./',
                        help='Data disk dir')
    parser.add_argument('--env', type=str,
                        default='PongNoFrameskip-v4')
    parser.add_argument('--alg', type=str, default='PPO2',
                        choices=['ACER', 'PPO2', 'GeDISC'],
                        help='Experiment name')
    parser.add_argument('--allow_eval', action='store_true',
                        help='Whether to eval agent')
    parser.add_argument('--save_model', action='store_true',
                        help='Whether to save model')
    parser.add_argument('--total_steps', type=float, default=1e6,
                        help='Total steps trained')
    parser.add_argument('--seed', type=int, default=0,
                        help='Random seed')
    parser.add_argument('--uniform', action='store_true',
                        help='Total steps trained')
    parser.add_argument('--num_env', type=int, default=8,
                        help='num of env')
    args = parser.parse_args()

    if not os.path.exists(args.data_dir):
        raise

    timestamp = time.strftime("%Y-%m-%d-%H_%M_%S", time.localtime(time.time()))
    base_name = args.alg + '_' + f'seed{args.seed}' + '_' + timestamp
    base_dir = os.path.join(
        args.data_dir, f"my_results/atari/{args.env}/{args.dir_name}/{base_name}")
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
    total_steps = int(args.total_steps)

    # Create dir
    summary_dir = os.path.join(base_dir, "tf1_summary")
    if not os.path.exists(summary_dir):
        os.makedirs(summary_dir)
    checkpoint_dir = os.path.join(base_dir, 'checkpoints')
    if not os.path.exists(checkpoint_dir):
        os.makedirs(checkpoint_dir)
    progress_csv = os.path.join(base_dir, 'progress.csv')
    log_txt = os.path.join(base_dir, 'log.txt')
    summary_writer = tf.compat.v1.summary.FileWriter(summary_dir)
    logger = Logger(progress_csv, log_txt, summary_writer)

    # Random seed
    tf.compat.v1.set_random_seed(args.seed)
    np.random.seed(args.seed)
    random.seed(args.seed)

    # Environment
    env = gym.make(args.env)
    env.seed(args.seed)
    env_eval = gym.make(args.env)
    env_eval.seed(args.seed)
    obs_shape = env.observation_space.shape
    ac_shape = env.action_space.shape

    env = make_vec_env(args.env, 'atari', num_env=args.num_env, seed=args.seed)
    env = VecFrameStack(env, nstack=4)

    gpu_options = tf.compat.v1.GPUOptions(allow_growth=True)
    sess = tf.compat.v1.Session(
        config=tf.compat.v1.ConfigProto(
            gpu_options=gpu_options,
            log_device_placement=False))
    # Fix save_weights and load_weights for keras.
    # tf.compat.v1.keras.backend.set_session(sess)

    # Tensorflow message must be put after sess.
    # DEBUG(0), INFO(1), WARNING(2), ERROR(3)
    # Combine os.environ['TF_CPP_MIN_LOG_LEVEL'] and tf.get_logger()
    tf.get_logger().setLevel('ERROR')
    gpu_list = tf.compat.v1.config.experimental.list_physical_devices('GPU')
    cprint(f'Tensorflow version: {tf.__version__}, '
           f'GPU available: {tf.test.is_gpu_available()}, '
           f'GPU count: {len(gpu_list)}\n'
           f'{gpu_list}\n',
           color='cyan', attrs=['bold'])

    # Hyperparameters in http://arxiv.org/abs/1709.06560
    if args.alg == 'ACER':
        import pg.agents.acer as ACER
        agent = ACER.ACERAgent(sess, env, horizon=50, gamma=0.99)
    elif args.alg == 'PPO2':
        import pg.agents.ppo2_atari as PPO2
        agent = PPO2.PPOAgent(sess, env, horizon=128, nenv=args.num_env,
                              gamma=0.99, lam=0.95, fixed_lr=False)
    elif args.alg == 'GeDISC':
        import pg.agents.gedisc_atari as GeDISC
        agent = GeDISC.PPOAgent(sess, env, horizon=128, nenv=args.num_env,
                                gamma=0.99, lam=0.95, fixed_lr=False, uniform=True)
    else:
        raise ValueError('Unknown agent: {}'.format(args.alg))

    # 1M // 2048 / 488 = 1
    log_interval = total_steps // agent.nbatch // 488

    # Actually, we won't use save_weights because it does not contain logstd.
    tf.compat.v1.keras.backend.set_session(sess)
    sess.run(tf.compat.v1.global_variables_initializer())
    if args.alg == 'ACER':
        sess.run(agent.init_avg_op)

    # Params
    horizon = agent.horizon
    nbatch = agent.nbatch

    cprint(f'Running experiment...\n'
           f'Env: {args.env}, Alg: {args.alg}\n'
           f'Logging dir: {base_dir}\n',
           color='cyan', attrs=['bold'])

    # Start
    start_time = time.time()
    obs = env.reset()
    # max_ep_ret = 0
    max_ep_len = env.spec.max_episode_steps
    ep_ret_buf = collections.deque(maxlen=100)
    ep_len_buf = collections.deque(maxlen=100)
    ep_len = 0
    ep_ret = 0.

    nupdates = total_steps // nbatch
    # Openai spinningup implementation
    for update in range(1, nupdates + 1):
        # Clear buffer
        for t in range(1, horizon + 1):
            ac, val, neglogp, mean = agent.select_action(obs)

            next_obs, rewards, dones, infos = env.step(ac)

            # done = done if ep_len < max_ep_len else False
            agent.buffer.store(obs=obs, ac=ac, rew=rewards, done=dones, obs2=next_obs,
                               val=val, neglogp=neglogp)

            obs = next_obs

            for info in infos:
                maybeepinfo = info.get('episode')
                if maybeepinfo:
                    ep_ret_buf.append(maybeepinfo['r'])
                    ep_len_buf.append(maybeepinfo['l'])

        # Progress ratio
        frac = 1.0 - (update - 1.0) / nupdates
        # Steps we have reached.
        step = update * nbatch

        agent.update(frac, logger)

        if update % log_interval == 0:
            avg_ep_ret = np.mean(ep_ret_buf)
            avg_ep_len = np.mean(ep_len_buf)

            logger.logkv("train/nupdates", update)
            logger.logkv("train/timesteps", step)
            logger.logkv("train/avgeplen", avg_ep_len)
            logger.logkv("train/avgepret", avg_ep_ret)

            logger.loginfo('env', args.env)
            logger.loginfo('alg', args.alg)
            logger.loginfo('totalsteps', total_steps)
            logger.loginfo('totalupdates', nupdates)
            logger.loginfo('horizon', horizon)
            logger.loginfo('nenv', args.num_env)
            logger.loginfo('nbatch', nbatch)
            logger.loginfo('progress', f'{update/nupdates:.1%}')

            logger.dumpkvs(timestep=step)

    time_delta = int(time.time() - start_time)
    m, s = divmod(time_delta, 60)
    h, m = divmod(m, 60)
    print(f'Time taken: {h:d}:{m:02d}:{s:02d}')
    print(f"Results saved into {base_dir}")
    logger.close()
    env.close()
    env_eval.close()


if __name__ == '__main__':
    main()
