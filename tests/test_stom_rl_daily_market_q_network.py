from __future__ import annotations

import math

import numpy as np

from stom_rl.daily_market_q_network import MarketQNetwork, q_loss_and_gradients


def test_cql_loss_supports_preregistered_four_action_allocation() -> None:
    # Given: one sample for every allocation action and a four-output network.
    network = MarketQNetwork.initialize(
        2,
        (4, 3),
        4,
        np.random.default_rng(20260810),
    )
    states = np.asarray(
        ((-1.0, 0.0), (-0.25, 0.0), (0.25, 0.0), (1.0, 0.0)),
        dtype=np.float64,
    )
    actions = np.asarray((0, 1, 2, 3), dtype=np.int64)
    targets = np.asarray((0.0, 0.1, 0.2, 0.3), dtype=np.float64)

    # When: the discrete CQL objective is evaluated.
    loss, gradients = q_loss_and_gradients(
        network,
        states,
        actions,
        targets,
        cql_alpha=1.0,
    )

    # Then: all action logits participate without binary-only shape assumptions.
    assert math.isfinite(loss)
    assert gradients.output_weight.shape == (3, 4)
    assert gradients.output_bias.shape == (4,)
