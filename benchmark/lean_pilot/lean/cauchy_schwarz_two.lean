import Mathlib
namespace MathesisPilot
theorem lean_cauchy_schwarz_two : ∀ (a b c d : ℝ), (a * c + b * d) ^ 2 ≤ (a ^ 2 + b ^ 2) * (c ^ 2 + d ^ 2) := by
  intro a
  intro b
  intro c
  intro d
  have h : 0 ≤ (a * d - b * c) ^ 2 := sq_nonneg (a * d - b * c)
  nlinarith [h]
end MathesisPilot
