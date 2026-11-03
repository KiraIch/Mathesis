import Mathlib
namespace MathesisHard
def sumTo : ℕ → ℕ
  | 0 => 0
  | n + 1 => (n + 1) + sumTo n

theorem lean_custom_sum_to : ∀ n : ℕ, 2 * sumTo n = n * (n + 1) := by
  intro n
  induction n with
  | zero => rfl
  | succ k ih =>
    simp only [sumTo]
    rw [mul_add, ih]
    ring
end MathesisHard
