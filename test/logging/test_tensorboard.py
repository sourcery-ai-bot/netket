import pytest

import glob

import netket as nk
from jax.nn.initializers import normal
from jax import numpy as jnp

from .. import common

pytestmark = common.skipif_mpi


@pytest.fixture()
def vstate(request):
    N = 8
    hi = nk.hilbert.Spin(1 / 2, N)

    ma = nk.models.RBM(
        alpha=1,
        param_dtype=float,
        hidden_bias_init=normal(),
        visible_bias_init=normal(),
    )

    return nk.vqs.MCState(
        nk.sampler.MetropolisLocal(hi),
        ma,
    )


def test_tblog(vstate, tmp_path):
    # skip test if tensorboardX not installed
    pytest.importorskip("tensorboardX")

    path = f"{str(tmp_path)}/dir1/dir2"

    log = nk.logging.TensorBoardLog(path)

    for i in range(10):
        log(i, {"Energy": jnp.array(1.0), "complex": jnp.array(1.0 + 1j)}, vstate)

    log.flush()
    del log

    files = glob.glob(f"{path}/*")
    assert files


def test_lazy_init(tmp_path):
    # skip test if tensorboardX not installed
    pytest.importorskip("tensorboardX")

    path = f"{str(tmp_path)}/dir1"

    nk.logging.TensorBoardLog(path)

    files = glob.glob(f"{path}/*")
    assert not files
