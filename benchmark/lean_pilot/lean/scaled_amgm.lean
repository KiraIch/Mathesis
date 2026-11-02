import Mathlib
namespace MathesisPilot
theorem lean_scaled_amgm : ∀ (k a b : ℝ), 2 * k * a * b ≤ a ^ 2 + k ^ 2 * b ^ 2 := by
  intro k
  intro a
  intro b
  have h : 0 ≤ (a - k * b) ^ 2 := sq_nonneg (a - k * b)
  nlinarith [h]
end MathesisPilot
