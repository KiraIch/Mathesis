import Mathlib
namespace MathesisHard
theorem lean_nat_tetra_triple_sum : ∀ n : ℕ, ∑ i ∈ Finset.range (n + 1), 3 * i * (i + 1) = n * (n + 1) * (n + 2) := by
  intro n
  induction n with | zero => simp | succ k ih => rw [Finset.sum_range_succ, ih]; ring
end MathesisHard
