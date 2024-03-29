import numpy as np


class ReplayBuffer:
    """
    A simple FIFO experience replay buffer for DDPG agents.
    """

    def __init__(self, obs_dim, ac_dim, size):
        self.obs1_buf = np.zeros((size,) + obs_dim, dtype=np.float32)
        self.obs2_buf = np.zeros((size,) + obs_dim, dtype=np.float32)
        self.acts_buf = np.zeros((size,) + ac_dim, dtype=np.float32)
        self.rews_buf = np.zeros(size, dtype=np.float32)
        self.done_buf = np.zeros(size, dtype=np.float32)
        self.ptr, self.size, self.max_size = 0, 0, size

    def store(self, obs, next_obs, act, rew, done):
        self.obs1_buf[self.ptr] = obs
        self.obs2_buf[self.ptr] = next_obs
        self.acts_buf[self.ptr] = act
        self.rews_buf[self.ptr] = rew
        self.done_buf[self.ptr] = done
        self.ptr = (self.ptr+1) % self.max_size
        self.size = min(self.size+1, self.max_size)

    def sample_batch(self, batch_size=32):
        idxs = np.random.randint(0, self.size, size=batch_size)
        return [self.obs1_buf[idxs],
                self.obs2_buf[idxs],
                self.acts_buf[idxs],
                self.rews_buf[idxs],
                self.done_buf[idxs]]
