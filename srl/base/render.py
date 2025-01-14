import logging
import time
from typing import Optional, Union

import numpy as np
from srl.base.define import PlayRenderMode, RenderMode
from srl.utils.render_functions import print_to_text, text_to_rgb_array

logger = logging.getLogger(__name__)


class IRender:
    def set_render_mode(self, mode: RenderMode) -> None:
        pass

    def render_terminal(self, **kwargs) -> None:
        pass

    def render_rgb_array(self, **kwargs) -> Optional[np.ndarray]:
        return None


class Render:
    def __init__(
        self,
        render_obj: IRender,
        font_name: str = "",
        font_size: int = 12,
    ) -> None:
        self.render_obj = render_obj
        self.font_name = font_name
        self.font_size = font_size
        self.interval = -1
        self.mode = PlayRenderMode.none

        self.fig = None
        self.ax = None
        self.screen = None

        self.print_str = ""
        self.rgb_array = None

    def reset(self, mode: Union[str, PlayRenderMode], interval: float = -1):
        self.interval = interval
        self.mode = PlayRenderMode.from_str(mode)
        self.render_obj.set_render_mode(PlayRenderMode.convert_render_mode(self.mode))

    def cache_reset(self):
        self.print_str = ""
        self.rgb_array = None

    # ----------------------------

    def get_dummy(self) -> Union[None, str, np.ndarray]:
        if self.mode == PlayRenderMode.none:
            return
        elif self.mode == PlayRenderMode.terminal:
            return
        elif self.mode == PlayRenderMode.ansi:
            return ""
        elif self.mode == PlayRenderMode.rgb_array:
            return np.zeros((4, 4, 3), dtype=np.uint8)
        elif self.mode == PlayRenderMode.window:
            return

    def render(self, **kwargs) -> Union[None, str, np.ndarray]:
        if self.mode == PlayRenderMode.none:
            return
        elif self.mode == PlayRenderMode.terminal:
            return self.render_terminal(**kwargs)
        elif self.mode == PlayRenderMode.ansi:
            return self.render_terminal(return_text=True, **kwargs)
        elif self.mode == PlayRenderMode.rgb_array:
            return self.render_rgb_array(**kwargs)
        elif self.mode == PlayRenderMode.window:
            return self.render_window(**kwargs)

    def render_terminal(self, return_text: bool = False, **kwargs) -> Union[None, str]:
        if return_text:
            if self.print_str == "":
                self.print_str = print_to_text(lambda: self.render_obj.render_terminal(**kwargs))
            return self.print_str
        else:
            self.render_obj.render_terminal(**kwargs)

    def render_rgb_array(self, **kwargs) -> np.ndarray:
        if self.rgb_array is None:
            self.rgb_array = self.render_obj.render_rgb_array(**kwargs)
        if self.rgb_array is None:
            text = print_to_text(lambda: self.render_obj.render_terminal(**kwargs))
            if text == "":
                return np.zeros((4, 4, 3), dtype=np.uint8)  # dummy
            self.rgb_array = text_to_rgb_array(text, self.font_name, self.font_size)
        return self.rgb_array.astype(np.uint8)

    def render_window(self, **kwargs) -> np.ndarray:
        rgb_array = self.render_rgb_array(**kwargs)

        """matplotlibを採用"""
        if self.fig is None:
            import matplotlib.pyplot as plt

            plt.ion()  # インタラクティブモードをオン
            self.fig, self.ax = plt.subplots()
            self.ax.axis("off")

            if self.interval > 0:
                self.t0 = time.time() - self.interval

        # interval たっていない場合は待つ
        if self.interval > 0:
            elapsed_time = time.time() - self.t0
            if elapsed_time < self.interval:
                time.sleep((self.interval - elapsed_time) / 1000)
            self.t0 = time.time()

        self.ax.imshow(rgb_array)
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()

        return rgb_array
