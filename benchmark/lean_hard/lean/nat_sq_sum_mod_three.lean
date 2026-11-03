import Mathlib
namespace MathesisHard
theorem lean_nat_sq_sum_mod_three : ∀ x y : ℕ, 3 ∣ x ^ 2 + y ^ 2 → 3 ∣ x ∧ 3 ∣ y := by
  intro x y h
  have h' : (x ^ 2 + y ^ 2) % 3 = 0 := Nat.mod_eq_zero_of_dvd h
  have hx : x % 3 = 0 ∨ x % 3 = 1 ∨ x % 3 = 2 := by omega
  have hy : y % 3 = 0 ∨ y % 3 = 1 ∨ y % 3 = 2 := by omega
  rcases hx with hx | hx | hx <;> rcases hy with hy | hy | hy <;>
    simp [Nat.add_mod, Nat.pow_mod, hx, hy] at h' ⊢
  all_goals omega
end MathesisHard
