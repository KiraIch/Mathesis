import Mathlib
namespace MathesisHard
theorem lean_nat_cube_lt_three_pow : ∀ n : ℕ, 4 ≤ n → n ^ 3 < 3 ^ n := by
  intro n hn
  induction n, hn using Nat.le_induction with
  | base => norm_num
  | succ k hk ih =>
    have key : (k + 1) ^ 3 ≤ 3 * k ^ 3 := by
      nlinarith [Nat.mul_le_mul hk hk, Nat.mul_le_mul (Nat.mul_le_mul hk hk) hk]
    rw [pow_succ 3 k]
    linarith
end MathesisHard
