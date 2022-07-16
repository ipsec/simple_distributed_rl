import logging
import pickle
import random
import time
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple, cast

import numpy as np
from srl.base.define import EnvAction, EnvObservationType, RLObservationType
from srl.base.env.base import EnvRun, SpaceBase
from srl.base.env.genre import TurnBase2Player
from srl.base.env.registration import register
from srl.base.env.spaces import BoxSpace, DiscreteSpace
from srl.base.rl.base import RuleBaseWorker, WorkerRun
from srl.base.rl.processor import Processor
from srl.utils.viewer import Viewer

logger = logging.getLogger(__name__)

register(
    id="Othello",
    entry_point=__name__ + ":Othello",
    kwargs={"W": 8, "H": 8},
)
register(
    id="Othello6x6",
    entry_point=__name__ + ":Othello",
    kwargs={"W": 6, "H": 6},
)


@dataclass
class Othello(TurnBase2Player):

    W: int = 8
    H: int = 8

    def __post_init__(self):
        self._player_index = 0
        self.viewer = None

    def get_field(self, x: int, y: int) -> int:
        if x < 0:
            return 9
        if x >= self.W:
            return 9
        if y < 0:
            return 9
        if y >= self.H:
            return 9
        return self.field[self.W * y + x]

    def set_field(self, x: int, y: int, n: int):
        self.field[self.W * y + x] = n

    def pos(self, x: int, y: int) -> int:
        return self.W * y + x

    def pos_decode(self, a: int) -> Tuple[int, int]:
        return a % self.W, a // self.W

    # ---------------------------------

    @property
    def action_space(self) -> DiscreteSpace:
        return DiscreteSpace(self.W * self.H)

    @property
    def observation_space(self) -> SpaceBase:
        return BoxSpace(
            low=-1,
            high=1,
            shape=(self.W * self.H,),
        )

    @property
    def observation_type(self) -> EnvObservationType:
        return EnvObservationType.DISCRETE

    @property
    def max_episode_steps(self) -> int:
        return self.W * self.H

    @property
    def player_index(self) -> int:
        return self._player_index

    def call_reset(self) -> np.ndarray:
        self.action = 0

        self._player_index = 0
        self.field = np.zeros(self.W * self.H, dtype=int)
        center_x = int(self.W / 2) - 1
        center_y = int(self.H / 2) - 1
        self.set_field(center_x, center_y, 1)
        self.set_field(center_x + 1, center_y + 1, 1)
        self.set_field(center_x + 1, center_y, -1)
        self.set_field(center_x, center_y + 1, -1)
        self.movable_dirs = [
            self._calc_movable_dirs(0),
            self._calc_movable_dirs(1),
        ]

        return self.field

    def backup(self) -> Any:
        return pickle.dumps(
            [
                self._player_index,
                self.W,
                self.H,
                self.field,
                self.movable_dirs,
            ]
        )

    def restore(self, data: Any) -> None:
        d = pickle.loads(data)
        self._player_index = d[0]
        self.W = d[1]
        self.H = d[2]
        self.field = d[3]
        self.movable_dirs = d[4]

    def _calc_movable_dirs(self, player_index) -> List[List[int]]:
        my_color = 1 if player_index == 0 else -1
        enemy_color = -my_color

        dirs_list = [[] for _ in range(self.W * self.H)]
        for y in range(self.H):
            for x in range(self.W):
                # 石が置ける場所のみ
                if self.get_field(x, y) != 0:
                    continue

                # (x, y, dir) dirはテンキーに対応
                for diff_x, diff_y, dir_ in [
                    (-1, 1, 1),
                    (0, 1, 2),
                    (1, 1, 3),
                    (1, 0, 6),
                    (1, -1, 9),
                    (0, -1, 8),
                    (-1, -1, 7),
                    (-1, 0, 4),
                ]:
                    tmp_x = x + diff_x
                    tmp_y = y + diff_y

                    # 1つは相手の駒がある
                    if self.get_field(tmp_x, tmp_y) != enemy_color:
                        continue
                    tmp_x += diff_x
                    tmp_y += diff_y

                    # 相手の駒移動
                    while self.get_field(tmp_x, tmp_y) == enemy_color:
                        tmp_x += diff_x
                        tmp_y += diff_y

                    # 相手の駒の後に自分の駒があるか
                    if self.get_field(tmp_x, tmp_y) == my_color:
                        dirs_list[self.pos(x, y)].append(dir_)

        return dirs_list

    def call_step(self, action: int) -> Tuple[np.ndarray, float, float, bool, dict]:
        self.action = action

        # --- error action
        if len(self.movable_dirs[self.player_index][action]) == 0:
            if self.player_index == 0:
                return self.field, -1, 0, True, {}
            else:
                return self.field, 0, -1, True, {}

        # --- step
        self._step(action)

        # --- 終了判定
        enemy_player = 1 if self.player_index == 0 else 0
        my_player = 0 if self.player_index == 0 else 1
        enemy_put_num = self.action_space.n - len(self.get_invalid_actions(enemy_player))
        my_put_num = self.action_space.n - len(self.get_invalid_actions(my_player))
        # 互いに置けないなら終了
        if enemy_put_num == 0 and my_put_num == 0:
            p1_count = len([f for f in self.field if f == 1])
            p2_count = len([f for f in self.field if f == -1])
            if p1_count > p2_count:
                r1 = 1
                r2 = -1
            elif p1_count < p2_count:
                r1 = -1
                r2 = 1
            else:
                r1 = r2 = 0
            return self.field, r1, r2, True, {"P1": p1_count, "P2": p2_count}

        # 相手が置けないならpass
        if enemy_put_num == 0:
            return self.field, 0, 0, False, {}

        # 手番交代
        self._player_index = enemy_player
        return self.field, 0, 0, False, {}

    def _step(self, action):

        # --- update
        x, y = self.pos_decode(action)
        my_color = 1 if self.player_index == 0 else -1
        self.field[action] = my_color

        # 移動方向はテンキー
        move_diff = {
            1: (-1, 1),
            2: (0, 1),
            3: (1, 1),
            6: (1, 0),
            9: (1, -1),
            8: (0, -1),
            7: (-1, -1),
            4: (-1, 0),
        }
        for movable_dir in self.movable_dirs[self.player_index][action]:
            diff_x, diff_y = move_diff[movable_dir]
            tmp_x = x + diff_x
            tmp_y = y + diff_y
            while self.get_field(tmp_x, tmp_y) != my_color:
                a = self.pos(tmp_x, tmp_y)
                self.field[a] = my_color
                tmp_x += diff_x
                tmp_y += diff_y

        # 置ける場所を更新
        self.movable_dirs = [
            self._calc_movable_dirs(0),
            self._calc_movable_dirs(1),
        ]

    def get_invalid_actions(self, player_index) -> List[int]:
        return [a for a in range(self.H * self.W) if len(self.movable_dirs[player_index][a]) == 0]

    def render_terminal(self, **kwargs) -> None:
        invalid_actions = self.get_invalid_actions(self.player_index)
        p1_count = len([f for f in self.field if f == 1])
        p2_count = len([f for f in self.field if f == -1])

        print("-" * (1 + self.W * 3))
        for y in range(self.H):
            s = "|"
            for x in range(self.W):
                a = self.pos(x, y)
                if self.field[a] == 1:
                    if self.action == a:
                        s += "*o|"
                    else:
                        s += " o|"
                elif self.field[a] == -1:
                    if self.action == a:
                        s += "*x|"
                    else:
                        s += " x|"
                elif a not in invalid_actions:
                    s += "{:2d}|".format(a)
                else:
                    s += "  |"
            print(s)
        print("-" * (1 + self.W * 3))
        print(f"O: {p1_count}, X: {p2_count}")
        if self.player_index == 0:
            print("next player: O")
        else:
            print("next player: X")

    def render_gui(self, **kwargs) -> None:
        self._render_pygame(**kwargs)

    def render_rgb_array(self, **kwargs) -> np.ndarray:
        return self._render_pygame(**kwargs)

    def _render_pygame(self, **kwargs) -> np.ndarray:
        WIDTH = 400
        HEIGHT = 400
        if self.viewer is None:
            self.viewer = Viewer(WIDTH, HEIGHT, fps=1)

        w_margin = 10
        h_margin = 10
        cell_w = int((WIDTH - w_margin * 2) / self.W)
        cell_h = int((HEIGHT - h_margin * 2) / self.H)
        invalid_actions = self.get_invalid_actions(self.player_index)

        self.viewer.draw_start((255, 255, 255))

        # --- cell
        for y in range(self.H):
            for x in range(self.W):
                center_x = int(w_margin + x * cell_w + cell_w / 2)
                center_y = int(h_margin + y * cell_h + cell_h / 2)
                left_top_x = w_margin + x * cell_w
                left_top_y = h_margin + y * cell_h

                self.viewer.draw_box(
                    left_top_x,
                    left_top_y,
                    cell_w,
                    cell_h,
                    fill_color=(0, 200, 0),
                    width=4,
                    line_color=(0, 0, 0),
                )

                a = x + y * self.W
                if self.field[a] == 1:  # o
                    if self.action == a:
                        width = 4
                        line_color = (200, 0, 0)
                    else:
                        width = 0
                        line_color = (0, 0, 0)
                    self.viewer.draw_circle(
                        center_x,
                        center_y,
                        int(cell_w * 0.3),
                        filled=True,
                        fill_color=(0, 0, 0),
                        width=width,
                        line_color=line_color,
                    )
                elif self.field[a] == -1:  # x
                    if self.action == a:
                        width = 4
                        line_color = (200, 0, 0)
                    else:
                        width = 0
                        line_color = (0, 0, 0)
                    self.viewer.draw_circle(
                        center_x,
                        center_y,
                        int(cell_w * 0.3),
                        filled=True,
                        fill_color=(255, 255, 255),
                        width=width,
                        line_color=line_color,
                    )
                elif a not in invalid_actions:
                    if self.player_index == 0:
                        color = (0, 0, 0)
                    else:
                        color = (255, 255, 255)
                    self.viewer.draw_circle(
                        center_x,
                        center_y,
                        int(cell_w * 0.1),
                        filled=True,
                        fill_color=color,
                    )

        self.viewer.draw_end()
        return self.viewer.get_rgb_array()

    def make_worker(self, name: str) -> Optional[RuleBaseWorker]:
        if name == "cpu":
            return Cpu()
        return None


class Cpu(RuleBaseWorker):
    cache = {}

    def __init__(self) -> None:
        self.max_depth = 2

        self.evals8x8 = [
            [30, -12, 0, -1, -1, 0, -12, 30],
            [-12, -15, -3, -3, -3, -3, -15, -12],
            [0, -3, 0, -1, -1, 0, -3, 0],
            [-1, -3, -1, -1, -1, -1, -3, -1],
            [-1, -3, -1, -1, -1, -1, -3, -1],
            [0, -3, 0, -1, -1, 0, -3, 0],
            [-12, -15, -3, -3, -3, -3, -15, -12],
            [30, -12, 0, -1, -1, 0, -12, 30],
        ]
        self.evals8x8 = np.array(self.evals8x8).flatten()
        assert self.evals8x8.shape == (64,)
        self.evals6x6 = [
            [30, -12, 0, 0, -12, 30],
            [-12, -15, -3, -3, -15, -12],
            [0, -3, 0, 0, -3, 0],
            [0, -3, 0, 0, -3, 0],
            [-12, -15, -3, -3, -15, -12],
            [30, -12, 0, 0, -12, 30],
        ]
        self.evals6x6 = np.array(self.evals6x6).flatten()
        assert self.evals6x6.shape == (36,)

    def call_on_reset(self, env: EnvRun, worker_run: WorkerRun) -> None:
        pass  #

    def call_policy(self, env: EnvRun, worker_run: WorkerRun) -> EnvAction:
        self._count = 0
        self.t0 = time.time()
        scores = self._negamax(env.get_original_env().copy())
        self._render_scores = scores
        self._render_count = self._count
        self._render_time = time.time() - self.t0

        scores = np.array(scores)
        action = int(random.choice(np.where(scores == scores.max())[0]))
        return action

    def _negamax(self, env: Othello, depth: int = 0):

        key = str(env.field)
        if key in Cpu.cache:
            return Cpu.cache[key]

        self._count += 1

        env_dat = env.backup()
        player_index = env.player_index
        valid_actions = env.get_valid_actions(player_index)

        scores = [-999.0 for _ in range(env.action_space.n)]
        for a in valid_actions:
            env.restore(env_dat)

            # env stepを実施
            _, r1, r2, done, _ = env.call_step(a)
            if done:
                # 終了状態なら報酬をスコアにする
                if player_index == 0:
                    scores[a] = r1 * 500
                else:
                    scores[a] = r2 * 500
            elif depth > self.max_depth:
                # 評価値を返す
                if env.W == 8:
                    scores[a] = np.sum(self.evals8x8 * env.field)
                elif env.W == 6:
                    scores[a] = np.sum(self.evals6x6 * env.field)
                else:
                    scores[a] = 0
                if player_index != 0:
                    scores[a] = -scores[a]
            else:
                is_enemy = player_index != env.player_index
                n_scores = self._negamax(env, depth + 1)
                if is_enemy:
                    scores[a] = -np.max(n_scores)
                else:
                    scores[a] = np.max(n_scores)

        Cpu.cache[key] = scores
        return scores

    def call_render(self, _env: EnvRun, worker_run: WorkerRun) -> None:
        env = cast(Othello, _env.get_original_env())
        valid_actions = env.get_valid_actions(env.player_index)

        print(f"- MinMax count: {self._render_count}, {self._render_time:.3f}s -")
        for y in range(env.H):
            s = "|"
            for x in range(env.W):
                a = x + y * env.W
                if a in valid_actions:
                    s += "{:6.1f}|".format(self._render_scores[a])
                else:
                    s += " " * 6 + "|"
            print(s)
        print()


class LayerProcessor(Processor):
    def change_observation_info(
        self,
        env_observation_space: SpaceBase,
        env_observation_type: EnvObservationType,
        rl_observation_type: RLObservationType,
        env: Othello,
    ) -> Tuple[SpaceBase, EnvObservationType]:
        observation_space = BoxSpace(
            low=0,
            high=1,
            shape=(2, env.H, env.W),
        )
        return observation_space, EnvObservationType.SHAPE3

    def process_observation(self, observation: np.ndarray, env: Othello) -> np.ndarray:
        # Layer0: my_player field (0 or 1)
        # Layer1: enemy_player field (0 or 1)
        if env.player_index == 0:
            my_field = 1
            enemy_field = -1
        else:
            my_field = -1
            enemy_field = 1
        _field = np.zeros((2, env.H, env.W))
        for y in range(env.H):
            for x in range(env.W):
                idx = x + y * env.W
                if observation[idx] == my_field:
                    _field[0][y][x] = 1
                elif observation[idx] == enemy_field:
                    _field[1][y][x] = 1
        return _field
