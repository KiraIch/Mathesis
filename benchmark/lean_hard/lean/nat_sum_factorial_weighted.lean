import Mathlib
namespace MathesisHard
theorem lean_nat_sum_factorial_weighted : ∀ n : ℕ, ∑ i ∈ Finset.range n, (i ^ 2 + i + 1) * Nat.factorial i = n * Nat.factorial n := by
  intro n
  induction n with
  | zero => simp
  | succ k ih =>
    have tele : (k + 1) * (k + 1).factorial = k * k.factorial + (k ^ 2 + k + 1) * k.factorial := by rw [Nat.factorial_succ]; ring
    rw [Finset.sum_range_succ, ih, tele]
end MathesisHard
