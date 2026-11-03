import Mathlib
namespace MathesisHard
theorem lean_real_additive_quad_five : ∀ f : ℝ → ℝ, (∀ x y, f (x + y) = f x + f y + 2 * x * y) → f 1 = 3 → f 5 = 35 := by
  intro f hf h1
  have h2 : f 2 = 8 := by
    have := hf 1 1
    norm_num at this
    linarith
  have h4 : f 4 = 24 := by
    have := hf 2 2
    norm_num at this
    linarith
  have := hf 4 1
  norm_num at this
  linarith
end MathesisHard
