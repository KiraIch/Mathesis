import Mathlib
namespace MathesisHard
theorem lean_set_r_image_inter_injective : ∀ (α β : Type) (f : α → β), (∀ A B : Set α, f '' (A ∩ B) = f '' A ∩ f '' B) → Function.Injective f := by
  intro α β f h x y hxy
  have key : f x ∈ f '' ({x} ∩ {y}) := by
    rw [h]
    exact ⟨⟨x, rfl, rfl⟩, ⟨y, rfl, hxy.symm⟩⟩
  obtain ⟨z, ⟨hz1, hz2⟩, _⟩ := key
  rw [← hz1, ← hz2]
end MathesisHard
