import Mathlib
namespace MathesisHard
def fib2 : ℕ → ℕ
  | 0 => 0
  | 1 => 1
  | n + 2 => fib2 n + fib2 (n + 1)

theorem lean_custom_fib2_bound : ∀ n : ℕ, fib2 n ≤ 2 ^ n := by
  intro n
  induction n using Nat.strong_induction_on with
  | _ n ih =>
    rcases n with _ | _ | k
    · simp [fib2]
    · simp [fib2]
    · have h1 : fib2 k ≤ 2 ^ k := ih k (by omega)
      have h2 : fib2 (k + 1) ≤ 2 ^ (k + 1) := ih (k + 1) (by omega)
      have h3 : 2 ^ (k + 1) = 2 ^ k * 2 := pow_succ 2 k
      have h4 : 2 ^ (k + 1 + 1) = 2 ^ k * 4 := by ring
      have h5 : 0 ≤ 2 ^ k := by positivity
      simp only [fib2]
      rw [h4]
      linarith
end MathesisHard
