"""
Tests for MOC (Maps of Content) processor.
"""

from knowledge_system.processors.moc import (
    MOCProcessor,
    Person,
    Tag,
    MentalModel,
    JargonTerm,
    Belief,
    MOCData,
    generate_moc,
)


class TestMOCProcessor:
    """Test MOC processor functionality."""

    def test_processor_initialization(self):
        """Test processor initialization."""
        processor = MOCProcessor()
        assert processor.name == "moc"
        assert ".md" in processor.supported_formats
        assert ".txt" in processor.supported_formats

    def test_validate_input(self, tmp_path):
        """Test input validation."""
        processor = MOCProcessor()

        # Valid markdown file
        md_file = tmp_path / "test.md"
        md_file.write_text("# Test")
        assert processor.validate_input(md_file) is True
        assert processor.validate_input(str(md_file)) is True

        # Valid list of files
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("Test content")
        assert processor.validate_input([md_file, txt_file]) is True

        # Invalid file
        assert processor.validate_input(tmp_path / "nonexistent.md") is False

        # Invalid type
        assert processor.validate_input(123) is False

    def test_can_process(self, tmp_path):
        """Test can_process method."""
        processor = MOCProcessor()

        md_file = tmp_path / "test.md"
        md_file.write_text("# Test")

        assert processor.can_process(md_file) is True
        assert processor.can_process(str(md_file)) is True
        assert processor.can_process(tmp_path / "test.txt") is True
        assert processor.can_process(tmp_path / "test.pdf") is False

    def test_process_dry_run(self, tmp_path):
        """Test dry run processing."""
        processor = MOCProcessor()

        # Create test file
        md_file = tmp_path / "test.md"
        md_file.write_text("# Test\n\nJohn Doe mentioned this.\n\n#tag1 #tag2")

        result = processor.process(md_file, dry_run=True)

        assert result.success is True
        assert result.dry_run is True
        assert "DRY RUN" in result.data
        assert result.metadata["files_count"] == 1

    def test_extract_people(self, tmp_path):
        """Test people extraction."""
        processor = MOCProcessor()
        moc_data = MOCData()

        content = """
        John Doe is mentioned here.
        Jane Smith also appears.
        John Doe is mentioned again.
        """

        processor._extract_people(content, "test.md", moc_data)

        assert len(moc_data.people) == 2
        john = next(p for p in moc_data.people if p.name == "John Doe")
        jane = next(p for p in moc_data.people if p.name == "Jane Smith")

        assert john.mention_count == 2
        assert jane.mention_count == 1
        assert "test.md" in john.mentions
        assert "test.md" in jane.mentions

    def test_extract_tags(self, tmp_path):
        """Test tag extraction."""
        processor = MOCProcessor()
        moc_data = MOCData()

        content = """
        This has #tag1 and #tag2.
        Also [[tag3]] and **tag4**.
        """

        processor._extract_tags(content, "test.md", moc_data)

        assert len(moc_data.tags) == 4
        tag_names = [t.name for t in moc_data.tags]
        assert "tag1" in tag_names
        assert "tag2" in tag_names
        assert "tag3" in tag_names
        assert "tag4" in tag_names

    def test_extract_mental_models(self, tmp_path):
        """Test mental model extraction."""
        processor = MOCProcessor()
        moc_data = MOCData()

        content = """
        The Pareto Principle is important.
        Also the **Eisenhower Matrix** - mental model for prioritization.
        """

        processor._extract_mental_models(content, "test.md", moc_data)

        assert len(moc_data.mental_models) >= 1
        pareto = next(
    (m for m in moc_data.mental_models if "Pareto" in m.name),
     None)
        assert pareto is not None
        assert "test.md" in pareto.files

    def test_extract_jargon(self, tmp_path):
        """Test jargon extraction."""
        processor = MOCProcessor()
        moc_data = MOCData()

        content = """
        The API is important.
        **Machine Learning** - AI subset for pattern recognition.
        `API` - Application Programming Interface.
        """

        processor._extract_jargon(content, "test.md", moc_data)

        assert len(moc_data.jargon) >= 2
        api = next((j for j in moc_data.jargon if j.term == "API"), None)
        ml = next(
    (j for j in moc_data.jargon if "Machine Learning" in j.term),
     None)

        assert api is not None
        assert ml is not None
        assert ml.definition is not None

    def test_extract_beliefs(self, tmp_path):
        """Test belief extraction."""
        processor = MOCProcessor()
        moc_data = MOCData()

        content = """
        I believe that AI will transform society.
        **Climate change is real** - evidence from multiple studies.
        Research shows that exercise improves health.
        """

        processor._extract_beliefs(content, "test.md", moc_data)

        assert len(moc_data.beliefs) >= 2
        ai_belief = next(
    (b for b in moc_data.beliefs if "AI" in b.claim), None)
        climate_belief = next(
            (b for b in moc_data.beliefs if "climate" in b.claim.lower()), None
        )

        assert ai_belief is not None
        assert climate_belief is not None
        assert ai_belief.epistemic_weight == 0.6
        assert "test.md" in ai_belief.sources

    def test_generate_people_page(self):
        """Test people page generation."""
        processor = MOCProcessor()

        people = [
            Person(
    name="John Doe",
    mentions=[
        "file1.md",
        "file2.md"],
         mention_count=2),
            Person(name="Jane Smith", mentions=["file1.md"], mention_count=1),
        ]

        content = processor._generate_people_page(people)

        assert "# People" in content
        assert "## John Doe" in content
        assert "## Jane Smith" in content
        assert "Mentioned in 2 files:" in content
        assert "[[file1]]" in content

    def test_generate_tags_page(self):
        """Test tags page generation."""
        processor = MOCProcessor()

        tags = [
            Tag(name="ai", files=["file1.md", "file2.md"], usage_count=2),
            Tag(name="ml", files=["file1.md"], usage_count=1),
        ]

        content = processor._generate_tags_page(tags)

        assert "# Tags" in content
        assert "## #ai" in content
        assert "## #ml" in content
        assert "Used in 2 files:" in content
        assert "[[file1]]" in content

    def test_generate_mental_models_page(self):
        """Test mental models page generation."""
        processor = MOCProcessor()

        models = [
            MentalModel(
                name="Pareto Principle", definition="80/20 rule", files=["file1.md"]
            ),
            MentalModel(name="Eisenhower Matrix", files=["file2.md"]),
        ]

        content = processor._generate_mental_models_page(models)

        assert "# Mental Models" in content
        assert "## Pareto Principle" in content
        assert "**Definition:** 80/20 rule" in content
        assert "## Eisenhower Matrix" in content

    def test_generate_jargon_page(self):
        """Test jargon page generation."""
        processor = MOCProcessor()

        jargon = [
            JargonTerm(
                term="API",
                definition="Application Programming Interface",
                files=["file1.md"],
            ),
            JargonTerm(term="ML", files=["file2.md"]),
        ]

        content = processor._generate_jargon_page(jargon)

        assert "# Jargon" in content
        assert "## API" in content
        assert "**Definition:** Application Programming Interface" in content
        assert "## ML" in content

    def test_generate_beliefs_yaml(self):
        """Test beliefs YAML generation."""
        processor = MOCProcessor()

        beliefs = [
            Belief(
                claim="AI will transform society",
                sources=["file1.md"],
                epistemic_weight=0.7,
                evidence_quality="high",
            )
        ]

        yaml_content = processor._generate_beliefs_yaml(beliefs)

        assert "claim: AI will transform society" in yaml_content
        assert "epistemic_weight: 0.7" in yaml_content
        assert "evidence_quality: high" in yaml_content

    def test_generate_main_moc(self):
        """Test main MOC generation."""
        processor = MOCProcessor()

        moc_data = MOCData(
            people=[Person(name="John Doe", mentions=["file1.md"])],
            tags=[Tag(name="ai", files=["file1.md"])],
            mental_models=[MentalModel(name="Pareto", files=["file1.md"])],
            jargon=[JargonTerm(term="API", files=["file1.md"])],
            beliefs=[Belief(claim="Test", sources=["file1.md"])],
            source_files=["file1.md"],
        )

        content = processor._generate_main_moc(moc_data, "topical", 3)

        assert "# Maps of Content" in content
        assert "Theme: topical" in content
        assert "Depth: 3" in content
        assert "**Source Files:** 1" in content
        assert "**People Mentioned:** 1" in content
        assert "See [[People]]" in content
        assert "See [[Tags]]" in content
        assert "See [[Mental Models]]" in content
        assert "See [[Jargon]]" in content
        assert "See `beliefs.yaml`" in content

    def test_full_processing_pipeline(self, tmp_path):
        """Test complete processing pipeline."""
        processor = MOCProcessor()

        # Create test file with various content
        test_content = """
        # Test Document

        John Doe discusses AI and machine learning.
        Jane Smith mentions the Pareto Principle.

        #ai #ml #productivity

        **Machine Learning** - subset of AI for pattern recognition.
        **API** - Application Programming Interface.

        I believe that AI will transform society.
        Research shows that exercise improves health.
        """

        test_file = tmp_path / "test.md"
        test_file.write_text(test_content)

        # Process the file
        result = processor.process(test_file, include_beliefs=True)

        assert result.success is True
        assert result.metadata["people_found"] >= 2
        assert result.metadata["tags_found"] >= 3
        assert result.metadata["mental_models_found"] >= 1
        assert result.metadata["jargon_found"] >= 2
        assert result.metadata["beliefs_found"] >= 2

        # Check generated files
        assert "People.md" in result.data
        assert "Tags.md" in result.data
        assert "Mental Models.md" in result.data
        assert "Jargon.md" in result.data
        assert "beliefs.yaml" in result.data
        assert "MOC.md" in result.data

    def test_convenience_function(self, tmp_path):
        """Test convenience function."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test\nJohn Doe mentions AI.\n#ai")

        result = generate_moc(
            [test_file], theme="topical", depth=2, include_beliefs=False
        )

        assert "People.md" in result
        assert "Tags.md" in result
        assert "MOC.md" in result
        assert "beliefs.yaml" not in result  # Beliefs disabled

    def test_template_support(self, tmp_path):
        """Test template support in MOC generation."""
        processor = MOCProcessor()

        # Create test file
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test\nAlice Johnson mentions AI.\n#ai")

        # Create template file
        template_content = "Custom MOC Template\nTheme: {theme}\nPeople: {people_count}"
        template_file = tmp_path / "template.txt"
        template_file.write_text(template_content)

        # Test with template in dry run mode
        result = processor.process(
    test_file, template=template_file, dry_run=True)

        assert result.success is True
        assert "template" in result.metadata
        assert result.metadata["template"] == str(template_file)
        assert "template" in result.data  # Should mention template in dry run message

        # Test actual processing with template
        result = processor.process(
    test_file,
    template=template_file,
     dry_run=False)

        assert result.success is True
        assert "template" in result.metadata
        assert result.metadata["template"] == str(template_file)
        assert "MOC.md" in result.data
        # Check that template content was processed (not just the raw template)
        assert "Custom MOC Template" in result.data["MOC.md"]

    def test_template_placeholder_replacement(self, tmp_path):
        """Test template placeholder replacement."""
        processor = MOCProcessor()

        # Create test file
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test\nAlice Johnson mentions AI.\n#ai")

        # Create template with placeholders
        template_content = """
        Theme: {theme}
        Depth: {depth}
        People: {people_count}
        Tags: {tags_count}
        Files: {source_files_count}
        """
        template_file = tmp_path / "template.txt"
        template_file.write_text(template_content)

        # Process with template
        result = processor.process(
            test_file, template=template_file, theme="hierarchical", depth=5
        )

        assert result.success is True
        assert "Theme: hierarchical" in result.data["MOC.md"]
        assert "Depth: 5" in result.data["MOC.md"]
        assert "People: 1" in result.data["MOC.md"]
        assert "Tags: 1" in result.data["MOC.md"]
        assert "Files: 1" in result.data["MOC.md"]

    def test_template_with_lists(self, tmp_path):
        """Test template with list placeholders."""
        processor = MOCProcessor()

        # Create test file with multiple items
        test_content = """
        # Test Document

        Alice Johnson discusses AI.
        Bob Smith mentions machine learning.

        #ai #ml #technology

        **Machine Learning** - subset of AI.
        **API** - Application Programming Interface.
        """
        test_file = tmp_path / "test.md"
        test_file.write_text(test_content)

        # Create template with list placeholders
        template_content = """
        # Custom MOC

        ## People Found:
        {people_list}

        ## Tags Found:
        {tags_list}

        ## Mental Models:
        {mental_models_list}

        ## Jargon:
        {jargon_list}
        """
        template_file = tmp_path / "template.txt"
        template_file.write_text(template_content)

        # Process with template
        result = processor.process(test_file, template=template_file)

        assert result.success is True
        moc_content = result.data["MOC.md"]
        assert "Alice Johnson" in moc_content
        assert "Bob Smith" in moc_content
        assert "#ai" in moc_content
        assert "#ml" in moc_content
        assert "Machine Learning" in moc_content
        assert "API" in moc_content

    def test_invalid_template_file(self, tmp_path):
        """Test behavior with invalid template file."""
        processor = MOCProcessor()

        # Create test file
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test\nJohn Doe mentions AI.\n#ai")

        # Test with non-existent template
        result = processor.process(test_file, template="nonexistent.txt")

        # Should fall back to default generation
        assert result.success is True
        assert "MOC.md" in result.data
        assert "# Maps of Content" in result.data["MOC.md"]

    def test_convenience_function_with_template(self, tmp_path):
        """Test convenience function with template."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test\nAlice Johnson mentions AI.\n#ai")

        template_file = tmp_path / "template.txt"
        template_file.write_text("Custom template: {theme}")

        result = generate_moc(
    [test_file],
    theme="topical",
     template=template_file)

        assert "MOC.md" in result
        assert "Custom template: topical" in result["MOC.md"]

    def test_error_handling(self):
        """Test error handling."""
        processor = MOCProcessor()

        # Test with non-existent file
        result = processor.process("nonexistent.md")
        assert result.success is False
        assert (
            "No input files provided" in result.errors
            or "File not found" in result.errors
        )


class TestMOCModels:
    """Test MOC data models."""

    def test_person_model(self):
        """Test Person model."""
        person = Person(
            name="John Doe", mentions=["file1.md", "file2.md"], mention_count=2
        )

        assert person.name == "John Doe"
        assert len(person.mentions) == 1
        assert person.mention_count == 2

    def test_tag_model(self):
        """Test Tag model."""
        tag = Tag(name="ai", files=["file1.md"], usage_count=1)

        assert tag.name == "ai"
        assert len(tag.files) == 1
        assert tag.usage_count == 1

    def test_mental_model_model(self):
        """Test MentalModel model."""
        model = MentalModel(
            name="Pareto Principle", definition="80/20 rule", files=["file1.md"]
        )

        assert model.name == "Pareto Principle"
        assert model.definition == "80/20 rule"
        assert len(model.files) == 1

    def test_jargon_term_model(self):
        """Test JargonTerm model."""
        jargon = JargonTerm(
            term="API",
            definition="Application Programming Interface",
            files=["file1.md"],
        )

        assert jargon.term == "API"
        assert jargon.definition == "Application Programming Interface"
        assert len(jargon.files) == 1

    def test_belief_model(self):
        """Test Belief model."""
        belief = Belief(
            claim="AI will transform society",
            sources=["file1.md"],
            epistemic_weight=0.8,
            evidence_quality="high",
        )

        assert belief.claim == "AI will transform society"
        assert len(belief.sources) == 1
        assert belief.epistemic_weight == 0.8
        assert belief.evidence_quality == "high"

    def test_moc_data_model(self):
        """Test MOCData model."""
        moc_data = MOCData(
            people=[Person(name="John Doe", mentions=["file1.md"])],
            tags=[Tag(name="ai", files=["file1.md"])],
            source_files=["file1.md"],
        )

        assert len(moc_data.people) == 1
        assert len(moc_data.tags) == 1
        assert len(moc_data.source_files) == 1
