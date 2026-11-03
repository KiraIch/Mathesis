import Mathlib
namespace MathesisHard
theorem lean_nat_odd_sum : ∀ n : ℕ, ∑ i ∈ Finset.range n, (2 * i + 1) = n ^ 2 := by
  intro n
  induction n with
  | zero => simp
  | succ k ih =>
    rw [Finset.sum_range_succ, ih]
    ring
end MathesisHard
