import warnings

import tensorflow as tf
import tensorflow.keras as keras
from tensorflow.keras import layers as kl


class DuelingNetworkBlock(keras.Model):
    def __init__(
        self,
        action_num: int,
        dense_units: int,
        dueling_type: str = "average",
        activation: str = "relu",
        enable_noisy_dense: bool = False,
        enable_time_distributed_layer: bool = False,
    ):
        super().__init__()
        self.dueling_type = dueling_type

        if enable_noisy_dense:
            import tensorflow_addons as tfa

            _Dense = tfa.layers.NoisyDense
        else:
            _Dense = kl.Dense

        # value
        self.v1 = _Dense(dense_units, activation=activation, kernel_initializer="he_normal")
        self.v2 = _Dense(1, kernel_initializer="truncated_normal", bias_initializer="truncated_normal", name="v")

        # advance
        self.adv1 = _Dense(dense_units, activation=activation, kernel_initializer="he_normal")
        self.adv2 = _Dense(
            action_num, kernel_initializer="truncated_normal", bias_initializer="truncated_normal", name="adv"
        )

        self.enable_time_distributed_layer = enable_time_distributed_layer
        if enable_time_distributed_layer:
            self.v1 = kl.TimeDistributed(self.v1)
            self.v2 = kl.TimeDistributed(self.v2)
            self.adv1 = kl.TimeDistributed(self.adv1)
            self.adv2 = kl.TimeDistributed(self.adv2)

    def call(self, x, training=False):
        v = self.v1(x, training=training)
        v = self.v2(v, training=training)
        adv = self.adv1(x, training=training)
        adv = self.adv2(adv, training=training)

        if self.enable_time_distributed_layer:
            axis = 2
        else:
            axis = 1

        if self.dueling_type == "average":
            x = v + adv - tf.reduce_mean(adv, axis=axis, keepdims=True)
        elif self.dueling_type == "max":
            x = v + adv - tf.reduce_max(adv, axis=axis, keepdims=True)
        elif self.dueling_type == "":  # naive
            x = v + adv
        else:
            raise ValueError("dueling_network_type is undefined")

        return x

    def build(self, input_shape):
        self.__input_shape = input_shape
        super().build(self.__input_shape)

    def init_model_graph(self, name: str = ""):
        x = kl.Input(shape=self.__input_shape[1:])
        name = self.__class__.__name__ if name == "" else name
        keras.Model(inputs=x, outputs=self.call(x), name=name)


def create_dueling_network_layers(
    c,
    action_num: int,
    dense_units: int,
    dueling_type: str,
    activation: str = "relu",
    enable_noisy_dense: bool = False,
):
    #warnings.warn(
    #    "'FunctionalAPI' was changed to 'SubclassingAPI'. This function will be removed in the next update.",
    #    DeprecationWarning,
    #)

    if enable_noisy_dense:
        import tensorflow_addons as tfa

        _Dense = tfa.layers.NoisyDense
    else:
        _Dense = kl.Dense

    # value
    v = _Dense(dense_units, activation=activation, kernel_initializer="he_normal")(c)
    v = _Dense(1, kernel_initializer="truncated_normal", bias_initializer="truncated_normal", name="v")(v)

    # advance
    adv = _Dense(dense_units, activation=activation, kernel_initializer="he_normal")(c)
    adv = _Dense(action_num, kernel_initializer="truncated_normal", bias_initializer="truncated_normal", name="adv")(
        adv
    )

    if dueling_type == "average":
        c = v + adv - tf.reduce_mean(adv, axis=1, keepdims=True)
    elif dueling_type == "max":
        c = v + adv - tf.reduce_max(adv, axis=1, keepdims=True)
    elif dueling_type == "":  # naive
        c = v + adv
    else:
        raise ValueError("dueling_network_type is undefined")

    return c
