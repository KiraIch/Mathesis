import Mathlib
namespace MathesisHard
theorem lean_nat_cube_sum : ∀ n : ℕ, 4 * ∑ i ∈ Finset.range (n + 1), i ^ 3 = (n * (n + 1)) ^ 2 := by
  intro n
  induction n with
  | zero => simp
  | succ k ih =>
    rw [Finset.sum_range_succ, mul_add, ih]
    ring
end MathesisHard
