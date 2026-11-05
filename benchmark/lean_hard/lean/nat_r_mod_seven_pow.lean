import Mathlib
namespace MathesisHard
theorem lean_nat_r_mod_seven_pow : ∀ n : ℕ, 7 ∣ 3 ^ (2 * n + 1) + 2 ^ (n + 2) := by
  have key : ∀ n : ℕ, 3 ^ (2 * n + 1) + 2 ^ (n + 2) = 3 * 9 ^ n + 4 * 2 ^ n := by
    intro n
    rw [pow_succ, pow_mul, pow_add]
    norm_num
    ring
  intro n
  have h : 9 ^ n % 7 = 2 ^ n % 7 := by
    rw [Nat.pow_mod]
  rw [key n]
  omega
end MathesisHard
