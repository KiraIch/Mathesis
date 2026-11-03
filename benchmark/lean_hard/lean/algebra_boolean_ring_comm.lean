import Mathlib
namespace MathesisHard
theorem lean_algebra_boolean_ring_comm : ∀ (R : Type) [Ring R], (∀ x : R, x * x = x) → ∀ x y : R, x * y = y * x := by
  intro R _ h x y
  have h2 : ∀ z : R, z + z = 0 := by
    intro z
    have h4 := h (z + z)
    have e : (z + z) * (z + z) = z + z + z + z := by
      have : (z + z) * (z + z) = z * z + z * z + z * z + z * z := by noncomm_ring
      rw [this, h z]
    rw [e] at h4
    calc z + z = (z + z + z + z) - (z + z) := by abel
      _ = 0 := by rw [h4]; exact sub_self _
  have h3 : x * y + y * x = 0 := by
    have h4 := h (x + y)
    have e : (x + y) * (x + y) = x + x * y + y * x + y := by
      have : (x + y) * (x + y) = x * x + x * y + y * x + y * y := by noncomm_ring
      rw [this, h x, h y]
    rw [e] at h4
    calc x * y + y * x = (x + x * y + y * x + y) - (x + y) := by abel
      _ = 0 := by rw [h4]; exact sub_self _
  exact (eq_neg_of_add_eq_zero_left h3).trans (eq_neg_of_add_eq_zero_left (h2 (y * x))).symm
end MathesisHard
