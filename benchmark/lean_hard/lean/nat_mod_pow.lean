import Mathlib
namespace MathesisHard
theorem lean_nat_mod_pow : ∀ n : ℕ, 8 ^ n % 7 = 1 := by
  intro n
  rw [Nat.pow_mod]
  norm_num
end MathesisHard
