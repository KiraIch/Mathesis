import Mathlib
namespace MathesisHard
theorem lean_algebra_r_sq_hom_comm : ∀ (G : Type) [Group G], (∀ a b : G, (a * b) ^ 2 = a ^ 2 * b ^ 2) → ∀ a b : G, a * b = b * a := by
  intro G _ h a b
  have key : a * (b * a) * b = a * (a * b) * b := by
    have h1 := h a b
    simp only [sq, mul_assoc] at h1 ⊢
    exact h1
  have := mul_left_cancel (mul_right_cancel key)
  exact this.symm
end MathesisHard
