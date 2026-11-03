import Mathlib
namespace MathesisHard
theorem lean_nat_dvd3_cubic : ∀ n : ℕ, 3 ∣ n ^ 3 + 2 * n := by
  intro n
  induction n with
  | zero => simp
  | succ k ih =>
    have h : (k + 1) ^ 3 + 2 * (k + 1) = (k ^ 3 + 2 * k) + 3 * (k ^ 2 + k + 1) := by ring
    rw [h]
    exact dvd_add ih (dvd_mul_right 3 _)
end MathesisHard
