import Mathlib
namespace MathesisHard
theorem lean_algebra_commutator_cancel : ∀ (G : Type) [Group G] (a b : G), a * b * a⁻¹ * b⁻¹ * b = a * b * a⁻¹ := by
  intro G _ a b
  group
end MathesisHard
