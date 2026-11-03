import Mathlib
namespace MathesisHard
theorem lean_nat_dvd_sq_sum_eq : ∀ a b : ℕ, 0 < a → 0 < b → a * b ∣ a ^ 2 + b ^ 2 → a = b := by
  intro a b ha hb h
  have hg : 0 < Nat.gcd a b := Nat.gcd_pos_of_pos_left _ ha
  obtain ⟨g, x, y, hg0, hxy, rfl, rfl⟩ := Nat.exists_coprime' hg
  have h1 : g * g * (x * y) ∣ g * g * (x ^ 2 + y ^ 2) := by
    have e1 : g * g * (x * y) = x * g * (y * g) := by ring
    have e2 : g * g * (x ^ 2 + y ^ 2) = (x * g) ^ 2 + (y * g) ^ 2 := by ring
    rw [e1, e2]; exact h
  have h2 : x * y ∣ x ^ 2 + y ^ 2 := Nat.dvd_of_mul_dvd_mul_left (Nat.mul_pos hg0 hg0) h1
  have hx : x ∣ y ^ 2 := by
    have : x ∣ x ^ 2 + y ^ 2 := (Dvd.intro _ rfl).trans h2
    exact (Nat.dvd_add_right (dvd_pow_self x (by norm_num))).mp this
  have hy : y ∣ x ^ 2 := by
    have : y ∣ x ^ 2 + y ^ 2 := (Dvd.intro_left _ rfl).trans h2
    exact (Nat.dvd_add_left (dvd_pow_self y (by norm_num))).mp this
  have hx1 : x = 1 := Nat.Coprime.eq_one_of_dvd (Nat.Coprime.pow_right 2 hxy) hx
  have hy1 : y = 1 := Nat.Coprime.eq_one_of_dvd (Nat.Coprime.pow_right 2 hxy.symm) hy
  rw [hx1, hy1]
end MathesisHard
