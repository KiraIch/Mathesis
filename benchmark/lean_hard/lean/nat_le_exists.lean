import Mathlib
namespace MathesisHard
theorem lean_nat_le_exists : ∀ a b : ℕ, a ≤ b → ∃ c, b = a + c := by
  intro a b h
  exact ⟨b - a, by omega⟩
end MathesisHard
