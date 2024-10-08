import torch
from sim.conn import client
import gymnasium as gym
import argparse
import importlib
import os
from pathlib import Path
import numpy as np
import time
from sim.utils import show_img
import wandb

DEVICE = "cuda" if torch.cuda.is_available() else "auto"
IMG_SHAPE = (80, 80, 1)
TARGET = [30, -30, -5]
ENV_ID = "DroneSim-v1"
NUM_EPISODES = 600
# Each model may use different hyper params
hyper_params = {
    "learning_rate": 0.0003,
    "buffer_size": 200_000,
    "learning_starts": 100,
    "batch_size": 256,
    "tau": 0.005,
    "gamma": 0.99,
    "train_freq": 1,
    "gradient_steps": -1,
    "action_noise": None,
    "policy_kwargs": None,
    "verbose": 0,
    "seed": None,
    "_init_setup_model": True,
}

parser = argparse.ArgumentParser()
parser.add_argument("-model", choices=["dqn", "a2c", "ppo", "ddpg", "sac", "td3"])
parser.add_argument("-steps_per_ep", type=int)
parser.add_argument("-p", action="store_true")


def train(model, env: gym.Env, hyper_params: dict, max_ep_steps: int):
    m = model("CnnPolicy", env, device=DEVICE, tensorboard_log=f"data/{model.__name__}")
    m.learn(total_timesteps=max_ep_steps * NUM_EPISODES, progress_bar=True)
    m.save(f"model/{model.__name__}{time.time()}.zip")


def predict(model, env: gym.Env, max_steps: int):
    m = model.load(sorted([os.path.join("model", Path(x).stem) for x in os.listdir("model") if x.startswith(model.__name__)])[-1])
    obs, _ = env.reset()

    wandb.init(
        project= "UAV",
        config={
        "learning_rate": hyper_params["learning_rate"],
        "buffer_size": hyper_params["buffer_size"],
        "learning_starts": hyper_params["learning_starts"],
        "batch_size": hyper_params["batch_size"],
        "tau": hyper_params["tau"],
        "gamma": hyper_params["gamma"],
        "train_freq": hyper_params["train_freq"],
        "gradient_steps": hyper_params["gradient_steps"],
        "action_noise": hyper_params["action_noise"],
        "policy_kwargs": hyper_params["policy_kwargs"],
        "verbose": hyper_params["verbose"],
        "seed": hyper_params["seed"],
        "_init_setup_model": hyper_params["_init_setup_model"],
        }
    )

    for step in range(max_steps):
        action, _states = m.predict(obs, deterministic=True)
        obs, rewards, dones, truncated, info = env.step(action)
        wandb.log({"rewards": rewards, "info": info})
    wandb.finish()



if __name__ == "__main__":
    args = parser.parse_args()
    model = getattr(importlib.import_module(f"stable_baselines3.{args.model}"), args.model.upper())
    # Register env
    gym.register(id=ENV_ID, entry_point="sim.drone_env:DroneEnv", order_enforce=True, max_episode_steps=args.steps_per_ep)
    # make env
    env = gym.make(ENV_ID, img_shape=IMG_SHAPE, client=client, target=np.array(TARGET))
    if os.environ.get("DEBUG"):
        print(gym.spec(ENV_ID))
    train(model, env, hyper_params, args.steps_per_ep) if not args.p else predict(model, env, args.steps_per_ep)
