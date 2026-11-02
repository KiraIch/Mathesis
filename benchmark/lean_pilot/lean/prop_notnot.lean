namespace MathesisPilot
theorem lean_prop_notnot : ∀ (P : Prop), P → ¬¬P := by
  intro P
  intro h
  intro hn
  exact hn h
end MathesisPilot
