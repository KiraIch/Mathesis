import Mathlib
namespace MathesisHard
theorem lean_nat_sum_bound : ∀ n : ℕ, ∑ i ∈ Finset.range n, (i + 1) ≤ n * n := by
  intro n
  induction n with
  | zero => simp
  | succ k ih =>
    rw [Finset.sum_range_succ]
    nlinarith [ih]
end MathesisHard
