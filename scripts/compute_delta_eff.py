"""Numerically compute Δ_eff and ϵ for our Hertzian potentials.

Paper PRX 2015 Eq. (8) + Appendix A:
    f_α(ρ) = ρ ∫_ρ^∞ dr · F_α(r) / sqrt(r² − ρ²)
    I_αβ  = ∫_0^∞ dρ · f_α(ρ) · f_β(ρ)              (2D systems)
    Δ_eff = I_nn / I_rn
    ϵ     = I_rr · I_nn / I_rn² − 1
    τ_∞   = sqrt[ ((1+Δ_eff)² + ϵ) / ((1−Δ_eff)² + ϵ) ]

For our Hertzian (paper §II.D), in reduced units (φ₀=r₀=1):
    F_r(r) = (1 − r)         for r < 1, else 0
    F_n(r) = (1 − r)²        for r < 1, else 0

If our numerical Δ_eff and ϵ disagree with paper's quoted 0.57 and 0.082,
then the asymptotic τ_∞ we should be aiming for is whatever WE compute,
not the paper's 3.1.
"""
import numpy as np
from scipy import integrate


# Reduced Hertzian, r0 = 1, phi0 = 1.
def F_r(r):
    return np.where(r < 1.0, 1.0 - r, 0.0)


def F_n(r):
    return np.where(r < 1.0, (1.0 - r) ** 2, 0.0)


def f_alpha(rho, F_func, r_max=1.0, n_pts=2000):
    """Scattering function f_alpha(rho) = rho * int_rho^r_max dr F(r) / sqrt(r^2 - rho^2).

    For rho >= r_max, the integral is 0 (force is 0 outside cutoff).
    The integrand has integrable singularity at r=rho (1/sqrt(r^2-rho^2)).
    Use substitution u = sqrt(r - rho) * sqrt(r + rho) (or just a fine grid + endpoint care).

    We use the standard trick: substitute t = sqrt(r^2 - rho^2), so r = sqrt(t^2 + rho^2),
    dr = t/sqrt(t^2+rho^2) dt, and the singularity vanishes:
        f(rho) = rho * int_0^t_max dt * F(sqrt(t^2+rho^2)) / sqrt(t^2+rho^2) * (correctly)
    Actually:
        ∫ F(r)/sqrt(r^2-rho^2) dr = ∫ F(sqrt(t^2+rho^2)) * (1) dt   (since dt = sqrt(r^2-rho^2)/r dr)
                                                                    Wait that gives F * dt / 1 — need to redo.

    Let r = rho * cosh(u), dr = rho * sinh(u) du, sqrt(r^2 - rho^2) = rho * sinh(u).
    Then dr / sqrt(r^2 - rho^2) = du. So:
        int_rho^r_max F(r) / sqrt(r^2 - rho^2) dr = int_0^acosh(r_max/rho) F(rho * cosh(u)) du.

    This is well-behaved.
    """
    if rho >= r_max:
        return 0.0
    u_max = np.arccosh(r_max / rho)
    u = np.linspace(0.0, u_max, n_pts)
    r_vals = rho * np.cosh(u)
    integrand = F_func(r_vals)
    return rho * np.trapezoid(integrand, u)


def main():
    print("Numerical Δ_eff and ϵ for our Hertzian potentials")
    print("(reduced units: r0=1, phi0=1)")
    print()

    # Sample f_r(rho) and f_n(rho) on a grid 0 < rho < 1.
    n_rho = 1000
    rho_vals = np.linspace(1e-4, 0.9999, n_rho)
    f_r_vals = np.array([f_alpha(rho, F_r) for rho in rho_vals])
    f_n_vals = np.array([f_alpha(rho, F_n) for rho in rho_vals])

    # I_alphabeta = ∫_0^∞ dρ f_α f_β   (2D form, paper Appendix A)
    I_rr = np.trapezoid(f_r_vals * f_r_vals, rho_vals)
    I_rn = np.trapezoid(f_r_vals * f_n_vals, rho_vals)
    I_nn = np.trapezoid(f_n_vals * f_n_vals, rho_vals)

    print(f"  I_rr = {I_rr:.6f}")
    print(f"  I_rn = {I_rn:.6f}")
    print(f"  I_nn = {I_nn:.6f}")
    print()

    delta_eff = I_nn / I_rn
    eps = I_rr * I_nn / (I_rn ** 2) - 1.0
    tau_inf = np.sqrt(((1.0 + delta_eff) ** 2 + eps) /
                       ((1.0 - delta_eff) ** 2 + eps))

    print(f"  Δ_eff = I_nn / I_rn       = {delta_eff:.4f}")
    print(f"  ϵ     = I_rr·I_nn/I_rn²−1 = {eps:.4f}")
    print(f"  τ_∞   = sqrt[(1+Δ)²+ϵ / (1−Δ)²+ϵ]  = {tau_inf:.4f}")
    print()
    print("Paper PRX 2015 Eq. (10) quotes:")
    print("  Δ_eff = 0.57")
    print("  ϵ     = 0.082")
    print("  τ_∞   = 3.1")
    print()
    print("Comparison:")
    print(f"  |our Δ_eff − paper| / paper = {abs(delta_eff - 0.57) / 0.57:.2%}")
    print(f"  |our ϵ − paper| / paper      = {abs(eps - 0.082) / 0.082:.2%}")
    print(f"  |our τ_∞ − paper| / paper    = {abs(tau_inf - 3.1) / 3.1:.2%}")

    # Cauchy inequality check: ϵ >= 0 by Cauchy-Schwarz on (f_r, f_n).
    cs_ratio = (I_rn ** 2) / (I_rr * I_nn)
    print()
    print(f"Cauchy-Schwarz check: I_rn²/(I_rr·I_nn) = {cs_ratio:.6f}  (must be ≤ 1; close to 1 means small ϵ)")


if __name__ == "__main__":
    main()
