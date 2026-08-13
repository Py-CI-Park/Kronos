"""Typed NumPy MLP, CQL loss, and Adam updates for binary Q learning."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import final

import numpy as np
from numpy.typing import NDArray

from .daily_market_rl_contract import DailyMarketRlContractError

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]


@dataclass(frozen=True, slots=True)
class NetworkForward:
    """Forward-pass values required by explicit backpropagation."""

    states: FloatArray
    first_pre_activation: FloatArray
    first_hidden: FloatArray
    second_pre_activation: FloatArray
    second_hidden: FloatArray
    q_values: FloatArray


@dataclass(frozen=True, slots=True)
class NetworkGradients:
    """One gradient array for every trainable network parameter."""

    first_weight: FloatArray
    first_bias: FloatArray
    second_weight: FloatArray
    second_bias: FloatArray
    output_weight: FloatArray
    output_bias: FloatArray


@final
class MarketQNetwork:
    """Mutable optimizer-owned MLP; evaluation only calls predict."""

    def __init__(
        self,
        first_weight: FloatArray,
        first_bias: FloatArray,
        second_weight: FloatArray,
        second_bias: FloatArray,
        output_weight: FloatArray,
        output_bias: FloatArray,
    ) -> None:
        self.first_weight = first_weight
        self.first_bias = first_bias
        self.second_weight = second_weight
        self.second_bias = second_bias
        self.output_weight = output_weight
        self.output_bias = output_bias

    @classmethod
    def initialize(
        cls,
        input_dimension: int,
        hidden_dimensions: tuple[int, int],
        action_count: int,
        generator: np.random.Generator,
    ) -> MarketQNetwork:
        """Initialize deterministic He-scaled weights and zero biases."""
        first, second = hidden_dimensions
        return cls(
            generator.normal(
                0.0, math.sqrt(2.0 / input_dimension), (input_dimension, first)
            ),
            np.zeros(first, dtype=np.float64),
            generator.normal(0.0, math.sqrt(2.0 / first), (first, second)),
            np.zeros(second, dtype=np.float64),
            generator.normal(0.0, math.sqrt(2.0 / second), (second, action_count)),
            np.zeros(action_count, dtype=np.float64),
        )

    def clone(self) -> MarketQNetwork:
        """Create an independent target-network snapshot."""
        return MarketQNetwork(
            self.first_weight.copy(),
            self.first_bias.copy(),
            self.second_weight.copy(),
            self.second_bias.copy(),
            self.output_weight.copy(),
            self.output_bias.copy(),
        )

    def copy_from(self, source: MarketQNetwork) -> None:
        """Hard-update all target parameters without replacing arrays."""
        np.copyto(self.first_weight, source.first_weight)
        np.copyto(self.first_bias, source.first_bias)
        np.copyto(self.second_weight, source.second_weight)
        np.copyto(self.second_bias, source.second_bias)
        np.copyto(self.output_weight, source.output_weight)
        np.copyto(self.output_bias, source.output_bias)

    def forward(self, states: FloatArray) -> NetworkForward:
        first_pre = states @ self.first_weight + self.first_bias
        first_hidden = np.maximum(first_pre, 0.0)
        second_pre = first_hidden @ self.second_weight + self.second_bias
        second_hidden = np.maximum(second_pre, 0.0)
        q_values = second_hidden @ self.output_weight + self.output_bias
        return NetworkForward(
            states, first_pre, first_hidden, second_pre, second_hidden, q_values
        )

    def predict(self, states: FloatArray) -> FloatArray:
        return self.forward(states).q_values

    def gradients(
        self, forward: NetworkForward, q_gradient: FloatArray
    ) -> NetworkGradients:
        output_weight = forward.second_hidden.T @ q_gradient
        output_bias = _sum_rows(q_gradient)
        second_hidden_gradient = q_gradient @ self.output_weight.T
        second_pre_gradient = second_hidden_gradient * (
            forward.second_pre_activation > 0.0
        )
        second_weight = forward.first_hidden.T @ second_pre_gradient
        second_bias = _sum_rows(second_pre_gradient)
        first_hidden_gradient = second_pre_gradient @ self.second_weight.T
        first_pre_gradient = first_hidden_gradient * (
            forward.first_pre_activation > 0.0
        )
        return NetworkGradients(
            first_weight=forward.states.T @ first_pre_gradient,
            first_bias=_sum_rows(first_pre_gradient),
            second_weight=second_weight,
            second_bias=second_bias,
            output_weight=output_weight,
            output_bias=output_bias,
        )


def q_loss_and_gradients(
    network: MarketQNetwork,
    states: FloatArray,
    actions: IntArray,
    targets: FloatArray,
    *,
    cql_alpha: float,
) -> tuple[float, NetworkGradients]:
    """Compute Huber TD loss plus the discrete conservative Q penalty."""
    forward = network.forward(states)
    rows = np.arange(actions.size)
    observed = forward.q_values[rows, actions]
    difference = observed - targets
    absolute = np.abs(difference)
    temporal = float(
        np.mean(np.where(absolute <= 1.0, 0.5 * difference**2, absolute - 0.5))
    )
    observed_gradient = (
        np.where(absolute <= 1.0, difference, np.sign(difference)) / actions.size
    )
    row_max_vector: FloatArray = np.asarray(
        np.max(forward.q_values, axis=1),
        dtype=np.float64,
    )
    row_max: FloatArray = np.reshape(row_max_vector, (-1, 1))
    shifted: FloatArray = forward.q_values - row_max
    exponentials: FloatArray = np.exp(shifted)
    exponential_sum: FloatArray = np.asarray(
        np.sum(exponentials, axis=1, keepdims=True),
        dtype=np.float64,
    )
    probabilities: FloatArray = exponentials / exponential_sum
    exponential_sum_vector: FloatArray = np.reshape(exponential_sum, (-1,))
    logsumexp: FloatArray = row_max_vector + np.log(exponential_sum_vector)
    conservative = float(np.mean(logsumexp - observed))
    q_gradient: FloatArray = probabilities * (cql_alpha / actions.size)
    q_gradient[rows, actions] += observed_gradient - (cql_alpha / actions.size)
    loss = float(temporal + cql_alpha * conservative)
    if not math.isfinite(loss):
        raise DailyMarketRlContractError("NONFINITE_TRAINING_LOSS")
    return loss, network.gradients(forward, q_gradient)


@final
class AdamOptimizer:
    """Stateful Adam updater whose mutation is limited to model optimization."""

    def __init__(self, network: MarketQNetwork) -> None:
        self.first = NetworkGradients(
            *(np.zeros_like(value) for value in _parameters(network))
        )
        self.second = NetworkGradients(
            *(np.zeros_like(value) for value in _parameters(network))
        )
        self.step_count = 0

    def step(
        self, network: MarketQNetwork, gradients: NetworkGradients, learning_rate: float
    ) -> None:
        self.step_count += 1
        updated_parameters: list[FloatArray] = []
        next_first: list[FloatArray] = []
        next_second: list[FloatArray] = []
        for parameter, gradient, first, second in zip(
            _parameters(network),
            _gradients(gradients),
            _gradients(self.first),
            _gradients(self.second),
            strict=True,
        ):
            first_value = 0.9 * first + 0.1 * gradient
            second_value = 0.999 * second + 0.001 * gradient**2
            corrected_first = first_value / (1.0 - 0.9**self.step_count)
            corrected_second = second_value / (1.0 - 0.999**self.step_count)
            updated_parameters.append(
                parameter
                - learning_rate * corrected_first / (np.sqrt(corrected_second) + 1e-8)
            )
            next_first.append(first_value)
            next_second.append(second_value)
        _assign_parameters(network, tuple(updated_parameters))
        self.first = NetworkGradients(*next_first)
        self.second = NetworkGradients(*next_second)


def _parameters(network: MarketQNetwork) -> tuple[FloatArray, ...]:
    return (
        network.first_weight,
        network.first_bias,
        network.second_weight,
        network.second_bias,
        network.output_weight,
        network.output_bias,
    )


def _sum_rows(values: FloatArray) -> FloatArray:
    return np.asarray(np.sum(values, axis=0), dtype=np.float64)


def _gradients(gradients: NetworkGradients) -> tuple[FloatArray, ...]:
    return (
        gradients.first_weight,
        gradients.first_bias,
        gradients.second_weight,
        gradients.second_bias,
        gradients.output_weight,
        gradients.output_bias,
    )


def _assign_parameters(network: MarketQNetwork, values: tuple[FloatArray, ...]) -> None:
    (
        network.first_weight,
        network.first_bias,
        network.second_weight,
        network.second_bias,
        network.output_weight,
        network.output_bias,
    ) = values


__all__ = [
    "AdamOptimizer",
    "FloatArray",
    "IntArray",
    "MarketQNetwork",
    "q_loss_and_gradients",
]
