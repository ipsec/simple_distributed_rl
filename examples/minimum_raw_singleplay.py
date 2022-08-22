from typing import Optional

import srl
from srl.base.env.base import EnvRun
from srl.base.env.singleplay_wrapper import SinglePlayEnvWrapper
from srl.base.rl.base import RLConfig, RLParameter, RLRemoteMemory
from srl.base.rl.singleplay_wrapper import SinglePlayWorkerWrapper


def _run_episode(
    env: EnvRun,
    rl_config: RLConfig,
    parameter: RLParameter,
    remote_memory: Optional[RLRemoteMemory],
    training: bool,
    rendering=False,
):
    worker = srl.rl.make_worker(rl_config, parameter, remote_memory, training=training, distributed=False)
    if training:
        trainer = srl.rl.make_trainer(rl_config, parameter, remote_memory)
    else:
        trainer = None

    # change single play interface
    env = SinglePlayEnvWrapper(env)
    worker = SinglePlayWorkerWrapper(worker)

    # reset
    state = env.reset()
    worker.on_reset(env)

    if rendering:
        print("step 0")
        env.render()

    while not env.done:

        # action
        action = worker.policy(env)

        # render
        if rendering:
            worker.render(env)

        # step
        state, reward, done, env_info = env.step(action)
        work_info = worker.on_step(env)

        # train
        if trainer is None:
            train_info = {}
        else:
            train_info = trainer.train()

        # render
        if rendering:
            print(
                "step {}, action {}, reward: {}, done: {}, info: {} {} {}".format(
                    env.step_num, action, env.step_rewards[0], env.done, env_info, work_info, train_info
                )
            )
            env.render()

    return env.step_num, env.episode_rewards[0]


def main():

    env_config = srl.envs.Config("Grid")
    rl_config = srl.rl.ql.Config()

    # env init
    env = srl.envs.make(env_config)

    # rl init
    rl_config.reset_config(env)
    parameter = srl.rl.make_parameter(rl_config)
    remote_memory = srl.rl.make_remote_memory(rl_config)

    # --- train loop
    for episode in range(10000):
        step, reward = _run_episode(env, rl_config, parameter, remote_memory, training=True)
        if episode % 1000 == 0:
            print(f"{episode} / 10000 episode, {step} step, {reward} reward")

    # --- render
    step, reward = _run_episode(env, rl_config, parameter, None, training=False, rendering=True)
    print(f"step: {step}, reward: {reward}")


if __name__ == "__main__":
    main()
