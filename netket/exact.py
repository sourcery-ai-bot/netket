# Copyright 2020, 2021 The NetKet Authors - All rights reserved.
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

from typing import Optional

import numpy as _np
from scipy.sparse.linalg import bicgstab as _bicgstab
from scipy.sparse.linalg import LinearOperator as _LinearOperator

from .operator import AbstractOperator as _AbstractOperator
from jax.experimental.sparse import JAXSparse as _JAXSparse


def lanczos_ed(
    operator: _AbstractOperator,
    *,
    k: int = 1,
    compute_eigenvectors: bool = False,
    matrix_free: bool = False,
    scipy_args: Optional[dict] = None,
):
    r"""Computes `first_n` smallest eigenvalues and, optionally, eigenvectors
    of a Hermitian operator using :meth:`scipy.sparse.linalg.eigsh`.

    Args:
        operator: NetKet operator to diagonalize.
        k: The number of eigenvalues to compute.
        compute_eigenvectors: Whether or not to return the
            eigenvectors of the operator. With ARPACK, not requiring the
            eigenvectors has almost no performance benefits.
        matrix_free: If true, matrix elements are computed on the fly.
            Otherwise, the operator is first converted to a sparse matrix.
        scipy_args: Additional keyword arguments passed to
            :meth:`scipy.sparse.linalg.eigvalsh`. See the Scipy documentation for further
            information.

    Returns:
        Either `w` or the tuple `(w, v)` depending on whether `compute_eigenvectors`
        is True.

        - w: Array containing the lowest `first_n` eigenvalues.
        - v: Array containing the eigenvectors as columns, such that`v[:, i]`
          corresponds to `w[i]`.

    Example:
        Test for 1D Ising chain with 8 sites.

        >>> import netket as nk
        >>> hi = nk.hilbert.Spin(s=1/2)**8
        >>> hamiltonian = nk.operator.Ising(hi, h=1.0, graph=nk.graph.Chain(8))
        >>> w = nk.exact.lanczos_ed(hamiltonian, k=3)
        >>> w
        array([-10.25166179, -10.05467898,  -8.69093921])
    """
    from scipy.sparse.linalg import eigsh

    actual_scipy_args = {}
    if scipy_args:
        actual_scipy_args.update(scipy_args)
    actual_scipy_args["which"] = "SA"
    actual_scipy_args["k"] = k
    actual_scipy_args["return_eigenvectors"] = compute_eigenvectors

    if matrix_free:
        # wrap the operator.to_linear_operator() in a scipy.sparse.linalg.LinearOperator
        n = operator.hilbert.n_states
        A = _LinearOperator(
            (n, n),
            operator.to_linear_operator().__matmul__,
            dtype=operator.dtype,
        )
    else:
        A = operator.to_sparse()
        if isinstance(A, _JAXSparse):
            # jax sparse arrays are not compatible with scipy eigsh.
            # wrap them in a scipy.sparse.linalg.LinearOperator
            A = _LinearOperator(A.shape, A.__matmul__, dtype=A.dtype)

    result = eigsh(A, **actual_scipy_args)

    return result[::-1] if not compute_eigenvectors else result


def full_ed(operator: _AbstractOperator, *, compute_eigenvectors: bool = False):
    """Computes all eigenvalues and, optionally, eigenvectors
    of a Hermitian operator by full diagonalization.

    Args:
        operator: NetKet operator to diagonalize.
        compute_eigenvectors: Whether or not to return the eigenvectors
            of the operator.

    Returns:
        Either `w` or the tuple `(w, v)` depending on whether `compute_eigenvectors`
        is True.

    Example:

        Test for 1D Ising chain with 8 sites.

        >>> import netket as nk
        >>> hi = nk.hilbert.Spin(s=1/2)**8
        >>> hamiltonian = nk.operator.Ising(hi, h=1.0, graph=nk.graph.Chain(8))
        >>> w = nk.exact.full_ed(hamiltonian)
        >>> w.shape
        (256,)
    """
    from numpy.linalg import eigh, eigvalsh

    dense_op = operator.to_dense()

    return eigh(dense_op) if compute_eigenvectors else eigvalsh(dense_op)


def steady_state(lindblad, *, sparse=True, method="ed", rho0=None, **kwargs):
    r"""Computes the numerically exact steady-state of a lindblad master equation.
    The computation is performed either through the exact diagonalization of the
    hermitian :math:`L^\dagger L` matrix, or by means of an iterative solver (bicgstabl)
    targeting the solution of the non-hermitian system :math:`L\rho = 0`
    and :math:`\mathrm{Tr}[\rho] = 1`.

    Note that for systems with 7 or more sites it is usually computationally impossible
    to build the full lindblad operator and therefore only `iterative` will work.

    Note that for systems with hilbert spaces with dimensions above 40k, tol
    should be set to a lower value if the steady state has non-trivial correlations.

    Args:
        lindblad: The lindbladian encoding the master equation.
        sparse: Whether to use sparse matrices (default: False for ed, True for
            iterative)
        method: 'ed' (exact diagonalization) or 'iterative' (iterative bicgstabl)
        rho0: starting density matrix for the iterative diagonalization (default: None)
        kwargs...: additional kwargs passed to bicgstabl

    For full docs please consult SciPy documentation at
    https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.linalg.bicgstab.html

    Keyword Args:
        maxiter: maximum number of iterations for the iterative solver (default: None)
        tol: The precision for the calculation (default: 1e-05)
        callback: User-supplied function to call after each iteration. It is called as
            callback(xk), where xk is the current solution vector

    Returns:
        The steady-state density matrix.
    """
    M = lindblad.hilbert.physical.n_states

    if method == "ed":
        if not sparse:
            from numpy.linalg import eigh
            from warnings import warn

            warn(
                """For reasons unknown to me, using dense diagonalisation on this
                matrix results in very low precision of the resulting steady-state
                since the update to numpy 1.9.
                We suggest using sparse=True, however, if you wish not to, you have
                been warned.
                Your digits are your responsibility now.
                """,
                stacklevel=2,
            )

            lind_mat = lindblad.to_dense()

            ldagl = lind_mat.T.conj() * lind_mat
            w, v = eigh(ldagl)

        else:
            from scipy.sparse.linalg import eigsh

            lind_mat = lindblad.to_sparse()
            ldagl = lind_mat.T.conj() * lind_mat

            w, v = eigsh(ldagl, which="SM", k=2)

        print("Minimum eigenvalue is: ", w[0])
        rho = v[:, 0].reshape((M, M))
        rho = rho / rho.trace()

    elif method == "iterative":
        # An extra row is added at the bottom of the therefore M^2+1 long array,
        # with the trace of the density matrix. This is needed to enforce the
        # trace-1 condition.
        L = lindblad.to_linear_operator(sparse=sparse, append_trace=True)

        # Initial density matrix ( + trace condition)
        Lrho_start = _np.zeros((M**2 + 1), dtype=L.dtype)
        if rho0 is None:
            Lrho_start[0] = 1.0
            Lrho_start[-1] = 1.0
        else:
            Lrho_start[:-1] = rho0.reshape(-1)
            Lrho_start[-1] = rho0.trace()

        # Target residual (everything 0 and trace 1)
        Lrho_target = _np.zeros((M**2 + 1), dtype=L.dtype)
        Lrho_target[-1] = 1.0

        # Iterative solver
        print("Starting iterative solver...")
        res, info = _bicgstab(L, Lrho_target, x0=Lrho_start, **kwargs)

        rho = res[:-1].reshape((M, M))
        if info == 0:
            print("Converged trace is ", rho.trace())
        elif info > 0:
            print("Failed to converge after ", info, " ( trace is ", rho.trace(), " )")
        elif info < 0:
            print("An error occurred: ", info)

    else:
        raise ValueError("method must be 'ed' or 'iterative'")

    return rho
