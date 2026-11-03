import Mathlib
namespace MathesisHard
theorem lean_nat_fib_sq_sum : ∀ n : ℕ, ∑ i ∈ Finset.range n, (Nat.fib (i + 1)) ^ 2 = Nat.fib n * Nat.fib (n + 1) := by
  intro n
  induction n with
  | zero => simp
  | succ k ih =>
    rw [Finset.sum_range_succ, ih]
    have h2 : Nat.fib (k + 2) = Nat.fib k + Nat.fib (k + 1) := Nat.fib_add_two
    rw [h2]
    ring
end MathesisHard
