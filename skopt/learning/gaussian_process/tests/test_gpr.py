import numpy as np
import pytest

from scipy import optimize

from sklearn.utils.testing import assert_almost_equal
from sklearn.utils.testing import assert_false
from sklearn.utils.testing import assert_true
from sklearn.utils.testing import assert_array_almost_equal
from sklearn.utils.testing import assert_array_equal

from skopt.learning import GaussianProcessRegressor
from skopt.learning.gaussian_process.kernels import RBF
from skopt.learning.gaussian_process.kernels import Matern
from skopt.learning.gaussian_process.kernels import WhiteKernel
from skopt.learning.gaussian_process.gpr import _param_for_white_kernel_in_Sum

rng = np.random.RandomState(0)
X = rng.randn(5, 5)
y = rng.randn(5)

rbf = RBF()
wk = WhiteKernel()
mat = Matern()
kernel1 = rbf
kernel2 = mat + rbf
kernel3 = mat * rbf
kernel4 = wk * rbf
kernel5 = mat + rbf * wk


def predict_wrapper(X, gpr):
    """Predict that can handle 1-D input"""
    X = np.expand_dims(X, axis=0)
    return gpr.predict(X, return_std=True)


@pytest.mark.fast_test
@pytest.mark.parametrize("kernel", [kernel1, kernel2, kernel3, kernel4])
def test_param_for_white_kernel_in_Sum(kernel):
    kernel_with_noise = kernel + wk
    wk_present, wk_param = _param_for_white_kernel_in_Sum(kernel + wk)
    assert_true(wk_present)
    kernel_with_noise.set_params(
        **{wk_param: WhiteKernel(noise_level=0.0)})
    assert_array_equal(kernel_with_noise(X), kernel(X))

    assert_false(_param_for_white_kernel_in_Sum(kernel5)[0])


@pytest.mark.fast_test
def test_noise_equals_gaussian():
    gpr1 = GaussianProcessRegressor(rbf + wk).fit(X, y)

    # gpr2 sets the noise component to zero at predict time.
    gpr2 = GaussianProcessRegressor(rbf, noise="gaussian").fit(X, y)
    assert_false(gpr1.noise_)
    assert_true(gpr2.noise_)
    assert_almost_equal(gpr1.kernel_.k2.noise_level, gpr2.noise_, 4)
    mean1, std1 = gpr1.predict(X, return_std=True)
    mean2, std2 = gpr2.predict(X, return_std=True)
    assert_array_almost_equal(mean1, mean2, 4)
    assert_false(np.any(std1 == std2))


@pytest.mark.fast_test
def test_mean_gradient():
    length_scale = np.arange(1, 6)
    X = rng.randn(10, 5)
    y = rng.randn(10)
    X_new = rng.randn(5)

    rbf = RBF(length_scale=length_scale, length_scale_bounds="fixed")
    gpr = GaussianProcessRegressor(rbf, random_state=0).fit(X, y)

    mean, std, mean_grad = gpr.predict(
        np.expand_dims(X_new, axis=0),
        return_std=True, return_cov=False, return_mean_grad=True)
    num_grad = optimize.approx_fprime(
        X_new, lambda x: predict_wrapper(x, gpr)[0], 1e-4)
    assert_array_almost_equal(mean_grad, num_grad, decimal=3)


@pytest.mark.fast_test
def test_std_gradient():
    length_scale = np.arange(1, 6)
    X = rng.randn(10, 5)
    y = rng.randn(10)
    X_new = rng.randn(5)

    rbf = RBF(length_scale=length_scale, length_scale_bounds="fixed")
    gpr = GaussianProcessRegressor(rbf, random_state=0).fit(X, y)

    _, _, _, std_grad = gpr.predict(
        np.expand_dims(X_new, axis=0),
        return_std=True, return_cov=False, return_mean_grad=True,
        return_std_grad=True)
    num_grad = optimize.approx_fprime(
        X_new, lambda x: predict_wrapper(x, gpr)[1], 1e-4)
    assert_array_almost_equal(std_grad, num_grad, decimal=3)


def test_gpr_handles_similar_points():
    """
    This tests whether our implementation of GPR
    does not crash when the covariance matrix whose
    inverse is calculated during fitting of the
    regressor is singular.
    Singular covariance matrix often indicates
    that same or very close points are explored
    during the optimization procedure.

    Essentially checks that the default value of `alpha` is non zero.
    """
    X = np.random.rand(8, 3)
    y = np.random.rand(8)

    X[:3, :] = 0.0
    y[:3] = 1.0

    model = GaussianProcessRegressor()
    # this fails if singular matrix is not handled
    model.fit(X, y)


@pytest.mark.fast_test
def test_gpr_uses_noise():
    """ Test that gpr is using WhiteKernel by default"""
    X = np.random.normal(size=[100, 2])
    Y = np.random.normal(size=[100])

    g_gaussian = GaussianProcessRegressor()
    g_gaussian.fit(X, Y)
    m, sigma = g_gaussian.predict(X[0:1], return_cov=True)

    assert sigma > 0
