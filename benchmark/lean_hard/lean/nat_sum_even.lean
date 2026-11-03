import Mathlib
namespace MathesisHard
theorem lean_nat_sum_even : ∀ n : ℕ, 2 ∣ ∑ i ∈ Finset.range n, i * (i + 1) := by
  intro n
  induction n with
  | zero => simp
  | succ k ih =>
    have h2 : 2 ∣ k * (k + 1) := (Nat.even_mul_succ_self k).two_dvd
    rw [Finset.sum_range_succ]
    exact dvd_add ih h2
end MathesisHard
