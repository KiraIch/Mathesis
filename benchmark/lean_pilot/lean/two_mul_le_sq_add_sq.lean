import Mathlib
namespace MathesisPilot
theorem lean_two_mul_le_sq_add_sq : ∀ (a b : ℝ), 2 * a * b ≤ a ^ 2 + b ^ 2 := by
  intro a
  intro b
  have h : 0 ≤ (a - b) ^ 2 := sq_nonneg (a - b)
  nlinarith [h]
end MathesisPilot
