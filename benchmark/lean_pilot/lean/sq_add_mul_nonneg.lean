import Mathlib
namespace MathesisPilot
theorem lean_sq_add_mul_nonneg : ∀ (a b : ℝ), 0 ≤ a ^ 2 + a * b + b ^ 2 := by
  intro a
  intro b
  have h1 : 0 ≤ (a + b) ^ 2 := sq_nonneg (a + b)
  have h2 : 0 ≤ (a - b) ^ 2 := sq_nonneg (a - b)
  nlinarith [h1, h2]
end MathesisPilot
