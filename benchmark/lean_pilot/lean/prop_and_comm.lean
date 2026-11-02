namespace MathesisPilot
theorem lean_prop_and_comm : ∀ (P Q : Prop), P ∧ Q → Q ∧ P := by
  intro P
  intro Q
  intro h
  have hP : P := And.left h
  have hQ : Q := And.right h
  exact And.intro hQ hP
end MathesisPilot
