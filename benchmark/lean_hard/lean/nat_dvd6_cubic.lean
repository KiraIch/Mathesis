import Mathlib
namespace MathesisHard
theorem lean_nat_dvd6_cubic : ∀ n : ℕ, 6 ∣ n ^ 3 + 5 * n := by
  intro n
  induction n with
  | zero => simp
  | succ k ih =>
    have h2 : 2 ∣ k * (k + 1) := (Nat.even_mul_succ_self k).two_dvd
    have h3 : 6 ∣ 3 * (k * (k + 1)) := by
      rw [show (6 : ℕ) = 3 * 2 by norm_num]
      exact mul_dvd_mul_left 3 h2
    have h : (k + 1) ^ 3 + 5 * (k + 1) = (k ^ 3 + 5 * k) + (3 * (k * (k + 1)) + 6) := by ring
    rw [h]
    exact dvd_add ih (dvd_add h3 (dvd_refl 6))
end MathesisHard
