import Mathlib
namespace MathesisPilot
theorem lean_add_sq_le_three : ∀ (a b c : ℝ), (a + b + c) ^ 2 ≤ 3 * (a ^ 2 + b ^ 2 + c ^ 2) := by
  intro a
  intro b
  intro c
  have h1 : 0 ≤ (a - b) ^ 2 := sq_nonneg (a - b)
  have h2 : 0 ≤ (b - c) ^ 2 := sq_nonneg (b - c)
  have h3 : 0 ≤ (c - a) ^ 2 := sq_nonneg (c - a)
  nlinarith [h1, h2, h3]
end MathesisPilot
