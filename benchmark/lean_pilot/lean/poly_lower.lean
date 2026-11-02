import Mathlib
import Mathesis.Defs
namespace MathesisPilot
theorem lean_poly_lower : ∀ (x : ℝ), 2 ≤ pilotPoly x := by
  intro x
  have h : 0 ≤ (x - 1) ^ 2 := sq_nonneg (x - 1)
  unfold pilotPoly
  nlinarith [h]
end MathesisPilot
