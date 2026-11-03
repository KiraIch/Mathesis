import Mathlib
namespace MathesisHard
theorem lean_custom_mod3_sum_bound : ∀ n : ℕ, ∑ i ∈ Finset.range n, i % 3 ≤ 2 * n := by
  intro n
  induction n with | zero => simp | succ k ih => rw [Finset.sum_range_succ]; have := Nat.mod_lt k (show 3 > 0 by norm_num); omega
end MathesisHard
