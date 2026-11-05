import Mathlib
namespace MathesisHard
theorem lean_nat_r_fifth_power_mod30 : ∀ n : ℕ, 30 ∣ n ^ 5 + 29 * n := by
  have key : ∀ n : ℕ, (n ^ 5 + 29 * n) % 30 = ((n % 30) ^ 5 + 29 * (n % 30)) % 30 := by
    intro n
    simp [Nat.add_mod, Nat.pow_mod, Nat.mul_mod]
  intro n
  have h : n % 30 < 30 := Nat.mod_lt _ (by norm_num)
  apply Nat.dvd_of_mod_eq_zero
  rw [key n]
  generalize n % 30 = r at h ⊢
  interval_cases r <;> norm_num
end MathesisHard
