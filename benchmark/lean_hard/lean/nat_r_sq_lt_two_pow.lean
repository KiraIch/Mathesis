import Mathlib
namespace MathesisHard
theorem lean_nat_r_sq_lt_two_pow : ∀ n : ℕ, 5 ≤ n → n ^ 2 < 2 ^ n := by
  have key : ∀ m : ℕ, 5 ≤ m → 2 * m + 1 < m ^ 2 := by
    intro m hm
    nlinarith
  intro n hn
  induction n, hn using Nat.le_induction with
  | base => norm_num
  | succ m hm ih =>
    have h := key m hm
    rw [pow_succ 2 m]
    nlinarith
end MathesisHard
