import Mathlib
namespace MathesisHard
theorem lean_nat_r_sq_sum_three_dvd : ∀ a b : ℕ, 3 ∣ a ^ 2 + b ^ 2 → 3 ∣ a ∧ 3 ∣ b := by
  have key : ∀ x : ℕ, (x ^ 2 % 3 = 0 ∧ x % 3 = 0) ∨ x ^ 2 % 3 = 1 := by
    intro x
    have h : x % 3 < 3 := Nat.mod_lt _ (by norm_num)
    have e : x ^ 2 % 3 = (x % 3) ^ 2 % 3 := by rw [Nat.pow_mod]
    interval_cases hx : x % 3 <;> simp_all
  intro a b h
  rcases key a with ⟨h1, h2⟩ | h1 <;> rcases key b with ⟨h3, h4⟩ | h3 <;> omega
end MathesisHard
