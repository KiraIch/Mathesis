import Mathlib
namespace MathesisHard
theorem lean_nat_shifted_odd_sum : ∀ n : ℕ, ∑ i ∈ Finset.range n, (2 * i + 3) = n ^ 2 + 2 * n := by
  intro n
  induction n with | zero => simp | succ k ih => rw [Finset.sum_range_succ, ih]; ring
end MathesisHard
