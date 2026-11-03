import Mathlib
namespace MathesisHard
theorem lean_nat_two_n1_le_three_pow : ∀ n : ℕ, 2 * n + 1 ≤ 3 ^ n := by
  intro n
  induction n with | zero => simp | succ k ih => rw [pow_succ]; omega
end MathesisHard
