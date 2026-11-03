import Mathlib
namespace MathesisHard
theorem lean_nat_cube_mod9_cases : ∀ n : ℕ, n ^ 3 % 9 = 0 ∨ n ^ 3 % 9 = 1 ∨ n ^ 3 % 9 = 8 := by
  intro n
  have h := Nat.mod_lt n (show 9 > 0 by norm_num)
  rw [Nat.pow_mod]
  interval_cases n % 9 <;> simp
end MathesisHard
