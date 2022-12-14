# GeDISC

Run GeDISC on Swimmer (MuJoCo) for 1M steps:

```c
CUDA_VISIBLE_DEVICES=0 PYTHONWARNINGS=ignore python run_pg_mujoco.py --alg GeDISC --env Swimmer-v2 --total_steps 1e6
```

Run GeDISC on Pong (Atari) for 10M steps (40M frames):

```c
CUDA_VISIBLE_DEVICES=0 PYTHONWARNINGS=ignore python run_pg_atari.py --alg GeDISC --env PongNoFrameskip-v4 --total_steps 1e7
```
