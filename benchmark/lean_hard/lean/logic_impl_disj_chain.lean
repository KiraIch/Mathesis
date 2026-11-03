import Mathlib
namespace MathesisHard
theorem lean_logic_impl_disj_chain : ∀ (P Q R : Prop), (P → Q) → (¬Q ∨ R) → P → R := by
  intro P Q R hpq h hp
  rcases h with hnq | hr
  · exact absurd (hpq hp) hnq
  · exact hr
end MathesisHard
