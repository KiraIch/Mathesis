import Mathlib
namespace MathesisHard
theorem lean_logic_cantor_predicate_diagonal : ∀ (α : Type) (f : α → α → Prop), ∃ g : α → Prop, ∀ a, g ≠ f a := by
  intro α f
  refine ⟨fun x => ¬ f x x, fun a h => ?_⟩
  have h1 : (¬ f a a) = f a a := congrFun h a
  exact not_iff_self (Iff.of_eq h1)
end MathesisHard
