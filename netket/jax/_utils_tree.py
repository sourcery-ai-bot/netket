# Copyright 2021 The NetKet Authors - All rights reserved.
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

from functools import reduce
from typing import Callable


import jax
import netket.jax as nkjax
from jax import numpy as jnp
from jax.tree_util import (
    register_pytree_node,
    tree_flatten,
    tree_unflatten,
    tree_map,
    tree_leaves,
)

from netket.utils.types import PyTree, Scalar
from netket.utils.numbers import is_scalar


def tree_ravel(pytree: PyTree) -> tuple[jnp.ndarray, Callable]:
    """Ravel (i.e. flatten) a pytree of arrays down to a 1D array.

    Args:
      pytree: a pytree to ravel

    Returns:
      A pair where the first element is a 1D array representing the flattened and
      concatenated leaf values, and the second element is a callable for
      unflattening a 1D vector of the same length back to a pytree of of the same
      structure as the input ``pytree``.
    """
    leaves, treedef = tree_flatten(pytree)
    flat, unravel_list = nkjax.vjp(_ravel_list, *leaves)
    unravel_pytree = lambda flat: tree_unflatten(treedef, unravel_list(flat))
    return flat, unravel_pytree


def _ravel_list(*lst):
    return jnp.concatenate([jnp.ravel(elt) for elt in lst]) if lst else jnp.array([])


def eval_shape(fun, *args, has_aux=False, **kwargs):
    """
    Returns the dtype of forward_fn(pars, v)
    """
    if has_aux:
        out, _ = jax.eval_shape(fun, *args, **kwargs)
    else:
        out = jax.eval_shape(fun, *args, **kwargs)
    return out


def tree_size(tree: PyTree) -> int:
    """
    Returns the sum of the size of all leaves in the tree.
    It's equivalent to the number of scalars in the pytree.
    """
    return sum(tree_leaves(tree_map(lambda x: x.size, tree)))


def tree_leaf_iscomplex(pars: PyTree) -> bool:
    """
    Returns true if at least one leaf in the tree has complex dtype.
    """
    return any(jax.tree_util.tree_leaves(jax.tree_map(jnp.iscomplexobj, pars)))


def tree_leaf_isreal(pars: PyTree) -> bool:
    """
    Returns true if at least one leaf in the tree has real dtype.
    """
    return any(jax.tree_util.tree_leaves(jax.tree_map(jnp.isrealobj, pars)))


def tree_ishomogeneous(pars: PyTree) -> bool:
    """
    Returns true if all leaves have real dtype or all leaves have complex dtype.
    """
    return not (tree_leaf_isreal(pars) and tree_leaf_iscomplex(pars))


@jax.jit
def tree_conj(t: PyTree) -> PyTree:
    r"""
    Conjugate all complex leaves. The real leaves are left untouched.
    Args:
        t: pytree
    """
    return jax.tree_map(lambda x: jax.lax.conj(x) if jnp.iscomplexobj(x) else x, t)


@jax.jit
def tree_dot(a: PyTree, b: PyTree) -> Scalar:
    r"""
    compute the dot product of two pytrees

    Args:
        a, b: pytrees with the same treedef

    Returns:
        A scalar equal the dot product of of the flattened arrays of a and b.
    """
    return jax.tree_util.tree_reduce(
        jax.numpy.add,
        jax.tree_map(jax.numpy.sum, jax.tree_map(jax.numpy.multiply, a, b)),
    )


@jax.jit
def tree_cast(x: PyTree, target: PyTree) -> PyTree:
    r"""
    cast x the types of target

    Args:
        x: a pytree with arrays as leaves
        target: a pytree with the same treedef as x
                where only the dtypes of the leaves are accessed
    Returns:
        A pytree where each leaf of x is cast to the dtype of the corresponding leaf in target.
        The imaginary part of complex leaves which are cast to real is discarded.
    """
    # astype alone would also work, however that raises ComplexWarning when casting complex to real
    # therefore the real is taken first where needed
    return jax.tree_map(
        lambda x, target: (x if jnp.iscomplexobj(target) else x.real).astype(
            target.dtype
        ),
        x,
        target,
    )


@jax.jit
def tree_axpy(a: Scalar, x: PyTree, y: PyTree) -> PyTree:
    r"""
    compute a * x + y

    Args:
      a: scalar
      x, y: pytrees with the same treedef
    Returns:
        The sum of the respective leaves of the two pytrees x and y
        where the leaves of x are first scaled with a.
    """
    if is_scalar(a):
        return jax.tree_map(lambda x_, y_: a * x_ + y_, x, y)
    else:
        return jax.tree_map(lambda a_, x_, y_: a_ * x_ + y_, a, x, y)


class RealImagTuple(tuple):
    """
    A special kind of tuple which marks complex parameters which were split.
    Behaves like a regular tuple.
    """

    @property
    def real(self):
        return self[0]

    @property
    def imag(self):
        return self[1]


register_pytree_node(
    RealImagTuple,
    lambda xs: (xs, None),
    lambda _, xs: RealImagTuple(xs),
)


def _tree_to_real(x):
    if not tree_leaf_iscomplex(x):
        return x
    # TODO find a way to make it a nop?
    # return jax.vmap(lambda y: jnp.array((y.real, y.imag)))(x)
    r = jax.tree_map(lambda x: x.real if jnp.iscomplexobj(x) else x, x)
    i = jax.tree_map(lambda x: x.imag if jnp.iscomplexobj(x) else None, x)
    return RealImagTuple((r, i))


def _tree_to_real_inverse(x):
    if isinstance(x, RealImagTuple):
        # not using jax.lax.complex because it would convert scalars to arrays
        return jax.tree_map(lambda re, im: re + 1j * im if im is not None else re, *x)
    else:
        return x


def tree_to_real(pytree: PyTree) -> tuple[PyTree, Callable]:
    """Replace all complex leaves of a pytree with a RealImagTuple of 2 real leaves.

    Args:
      pytree: a pytree to convert to real

    Returns:
      A pair where the first element is the converted real pytree,
      and the second element is a callable for converting back a real pytree
      to a complex pytree of of the same structure as the input pytree.
    """
    return _tree_to_real(pytree), _tree_to_real_inverse


def compose(*funcs):
    """
    function composition

    compose(f,g,h)(x) is equivalent to f(g(h(x)))
    """

    def _compose(f, g):
        return lambda *args, **kwargs: f(g(*args, **kwargs))

    return reduce(_compose, funcs)
