import Mathlib
namespace MathesisPilot
theorem lean_fourth_power : ∀ (a b : ℝ), a ^ 3 * b + a * b ^ 3 ≤ a ^ 4 + b ^ 4 := by
  intro a
  intro b
  have h1 : 0 ≤ (a - b) ^ 2 := sq_nonneg (a - b)
  have h2 : 0 ≤ a ^ 2 + a * b + b ^ 2 := by
    have g1 : 0 ≤ (a + b) ^ 2 := sq_nonneg (a + b)
    have g2 : 0 ≤ (a - b) ^ 2 := sq_nonneg (a - b)
    nlinarith [g1, g2]
  have h3 : 0 ≤ (a - b) ^ 2 * (a ^ 2 + a * b + b ^ 2) := mul_nonneg h1 h2
  nlinarith [h3]
end MathesisPilot
