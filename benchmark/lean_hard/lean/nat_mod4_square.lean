import Mathlib
namespace MathesisHard
theorem lean_nat_mod4_square : ∀ n : ℕ, n ^ 2 % 4 = 0 ∨ n ^ 2 % 4 = 1 := by
  intro n
  have h : n % 4 < 4 := Nat.mod_lt n (by norm_num)
  rw [Nat.pow_mod]
  interval_cases n % 4 <;> simp
end MathesisHard
