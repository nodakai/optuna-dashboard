import sys
from unittest.mock import patch

import numpy as np
import pytest


if sys.version_info >= (3, 8):
    from optuna_dashboard.preferential.samplers.gp import _one_side_trunc_norm_sampling
    import torch
else:
    pytest.skip("BoTorch dropped Python3.7 support", allow_module_level=True)


def test_one_side_trunc_norm_sampling() -> None:
    for lower in np.linspace(-10, 10, 100):
        assert _one_side_trunc_norm_sampling(torch.tensor([lower], dtype=torch.float64)) >= lower

    with patch.object(torch, "rand", return_value=torch.tensor([0.4], dtype=torch.float64)):
        sampled_value = _one_side_trunc_norm_sampling(torch.tensor([0.1], dtype=torch.float64))
        assert np.allclose(sampled_value.numpy(), 0.899967154837563)

    with patch.object(torch, "rand", return_value=torch.tensor([0.8], dtype=torch.float64)):
        sampled_value = _one_side_trunc_norm_sampling(torch.tensor([-2.3], dtype=torch.float64))
        assert np.allclose(sampled_value.numpy(), -0.8113606739551955)

    with patch.object(torch, "rand", return_value=torch.tensor([0.1], dtype=torch.float64)):
        sampled_value = _one_side_trunc_norm_sampling(torch.tensor([5], dtype=torch.float64))
        assert np.allclose(sampled_value.numpy(), 5.426934003050024)
