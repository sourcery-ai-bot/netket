# Copyright 2022 The NetKet Authors - All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import numpy as np

from netket.vqs import FullSumState, expect
from netket.stats import Stats

from .S2_operator import Renyi2EntanglementEntropy


@expect.dispatch
def Renyi2(vstate: FullSumState, op: Renyi2EntanglementEntropy):
    if op.hilbert != vstate.hilbert:
        raise TypeError("Hilbert spaces should match")

    state_qutip = vstate.to_qobj()

    N = vstate.hilbert.size

    if len(op.partition) in [N, 0]:
        out = 0
    else:
        mask = np.zeros(N, dtype=bool)
        mask[op.partition] = True

        rdm = state_qutip.ptrace(np.arange(N)[mask])

        n = 2
        out = np.log2(np.trace(np.linalg.matrix_power(rdm, n))) / (1 - n)
        out = np.absolute(out.real)

    return Stats(mean=out, error_of_mean=0.0, variance=0.0)
