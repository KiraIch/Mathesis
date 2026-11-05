import Mathlib
namespace MathesisHard
theorem lean_nat_r_sophie_germain_composite : ∀ m : ℕ, ¬ Nat.Prime ((m + 2) ^ 4 + 4) := by
  have key : ∀ m : ℕ, (m + 2) ^ 4 + 4 = ((m + 2) ^ 2 + 2 * (m + 2) + 2) * ((m + 1) ^ 2 + 1) := by
    intro m
    ring
  intro m
  rw [key m]
  apply Nat.not_prime_mul <;> nlinarith [sq_nonneg m, pow_pos (Nat.succ_pos m) 2]
end MathesisHard
